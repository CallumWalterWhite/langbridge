from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import sqlglot
from sqlglot import exp

from langbridge.packages.federation.models.plans import JoinRef, LogicalPlan, QueryType, TableRef
from langbridge.packages.federation.models.virtual_dataset import VirtualDataset, VirtualTableBinding


class QueryParsingError(ValueError):
    pass


@dataclass(slots=True)
class ParsedSql:
    expression: exp.Expression
    select: exp.Select


def parse_sql(sql: str, *, dialect: str = "tsql") -> ParsedSql:
    try:
        expression = sqlglot.parse_one(sql, read=dialect)
    except sqlglot.ParseError as exc:
        raise QueryParsingError(str(exc)) from exc

    select = _extract_select(expression)
    if select is None:
        raise QueryParsingError("Only SELECT/CTE queries are supported in federation v1.")

    return ParsedSql(expression=expression, select=select)


def logical_plan_from_sql(
    *,
    sql: str,
    virtual_dataset: VirtualDataset,
    dialect: str = "tsql",
    query_type: QueryType = QueryType.SQL,
) -> tuple[LogicalPlan, exp.Expression]:
    parsed = parse_sql(sql, dialect=dialect)
    select_expr = parsed.select

    table_map: dict[str, TableRef] = {}

    base_table = select_expr.args.get("from")
    if base_table is None or base_table.this is None:
        raise QueryParsingError("Query must include a FROM clause.")
    base_alias, base_binding = _resolve_table(base_table.this, virtual_dataset)
    table_map[base_alias] = _table_ref(alias=base_alias, binding=base_binding)

    joins: list[JoinRef] = []
    for join in select_expr.args.get("joins") or []:
        if not isinstance(join, exp.Join):
            continue
        alias, binding = _resolve_table(join.this, virtual_dataset)
        table_map[alias] = _table_ref(alias=alias, binding=binding)
        join_kind = _join_kind(join)
        on_expr = join.args.get("on")
        joins.append(
            JoinRef(
                left_alias=joins[-1].right_alias if joins else base_alias,
                right_alias=alias,
                join_type=join_kind,
                on_sql=on_expr.sql(dialect=dialect) if on_expr is not None else "1=1",
            )
        )

    where_expr = select_expr.args.get("where")
    having_expr = select_expr.args.get("having")
    group_expr = select_expr.args.get("group")
    order_expr = select_expr.args.get("order")

    logical_plan = LogicalPlan(
        query_type=query_type,
        sql=sql,
        from_alias=base_alias,
        tables=table_map,
        joins=joins,
        where_sql=where_expr.this.sql(dialect=dialect) if isinstance(where_expr, exp.Where) else None,
        having_sql=having_expr.this.sql(dialect=dialect) if isinstance(having_expr, exp.Having) else None,
        group_by_sql=[item.sql(dialect=dialect) for item in (group_expr.expressions if isinstance(group_expr, exp.Group) else [])],
        order_by_sql=[item.sql(dialect=dialect) for item in (order_expr.expressions if isinstance(order_expr, exp.Order) else [])],
        limit=_extract_int(select_expr.args.get("limit")),
        offset=_extract_int(select_expr.args.get("offset")),
        has_cte=select_expr.args.get("with") is not None,
    )
    return logical_plan, parsed.expression


def extract_required_columns(
    expression: exp.Expression,
    table_aliases: Iterable[str],
) -> tuple[dict[str, set[str]], bool]:
    aliases = set(table_aliases)
    required: dict[str, set[str]] = {alias: set() for alias in aliases}
    has_unqualified = False

    for star in expression.find_all(exp.Star):
        _ = star
        for alias in aliases:
            required[alias].add("*")

    for column in expression.find_all(exp.Column):
        column_name = column.name
        table_name = column.table
        if not column_name:
            continue
        if table_name and table_name in aliases:
            required[table_name].add(column_name)
        elif table_name:
            continue
        else:
            has_unqualified = True

    return required, has_unqualified


def split_conjunctive_predicates(where_clause: exp.Expression | None) -> list[exp.Expression]:
    if where_clause is None:
        return []

    predicates: list[exp.Expression] = []

    def _walk(node: exp.Expression) -> None:
        if isinstance(node, exp.And):
            _walk(node.left)
            _walk(node.right)
            return
        predicates.append(node)

    _walk(where_clause)
    return predicates


def predicate_aliases(predicate: exp.Expression, table_aliases: Iterable[str]) -> set[str]:
    aliases = set(table_aliases)
    referenced: set[str] = set()
    for column in predicate.find_all(exp.Column):
        if column.table in aliases:
            referenced.add(column.table)
    return referenced


def rewrite_tables_to_stage_sql(
    expression: exp.Expression,
    *,
    stage_tables: dict[str, str],
) -> str:
    def _replace(node: exp.Expression) -> exp.Expression:
        if not isinstance(node, exp.Table):
            return node
        alias = node.alias_or_name
        stage_table = stage_tables.get(alias)
        if stage_table is None:
            return node
        return exp.table_(stage_table, alias=alias, quoted=False)

    transformed = expression.transform(_replace)
    return transformed.sql(dialect="duckdb")


def _extract_select(expression: exp.Expression) -> exp.Select | None:
    if isinstance(expression, exp.Select):
        return expression
    if isinstance(expression, exp.Subqueryable):
        return expression if isinstance(expression, exp.Select) else None
    if isinstance(expression, exp.Union):
        return None
    if isinstance(expression, exp.With):
        body = expression.this
        return body if isinstance(body, exp.Select) else None
    return expression.find(exp.Select)


def _resolve_table(
    table_expression: exp.Expression,
    virtual_dataset: VirtualDataset,
) -> tuple[str, VirtualTableBinding]:
    if not isinstance(table_expression, exp.Table):
        raise QueryParsingError("Only table references are supported in FROM/JOIN clauses for v1.")

    alias = table_expression.alias_or_name
    table_name = table_expression.name
    schema_name = table_expression.db
    catalog_name = table_expression.catalog

    direct = virtual_dataset.tables.get(table_name)
    if direct is not None:
        return alias, direct

    candidates = []
    for table_key, binding in virtual_dataset.tables.items():
        if table_key == table_name:
            candidates.append(binding)
            continue
        if binding.table != table_name:
            continue
        if schema_name and (binding.schema or "") != schema_name:
            continue
        if catalog_name and (binding.catalog or "") != catalog_name:
            continue
        candidates.append(binding)

    if len(candidates) == 1:
        return alias, candidates[0]
    if not candidates:
        raise QueryParsingError(
            f"Table '{table_expression.sql()}' is not mapped in virtual dataset '{virtual_dataset.id}'."
        )
    raise QueryParsingError(f"Table '{table_expression.sql()}' has ambiguous source mappings.")


def _table_ref(*, alias: str, binding: VirtualTableBinding) -> TableRef:
    return TableRef(
        alias=alias,
        table_key=binding.table_key,
        source_id=binding.source_id,
        connector_id=str(binding.connector_id),
        schema=binding.schema,
        table=binding.table,
        catalog=binding.catalog,
    )


def _join_kind(join: exp.Join) -> str:
    kind = join.args.get("kind")
    if isinstance(kind, exp.Expression):
        value = kind.sql().lower()
    elif kind is not None:
        value = str(kind).lower()
    else:
        value = "inner"
    return value or "inner"


def _extract_int(limit_or_offset: exp.Expression | None) -> int | None:
    if limit_or_offset is None:
        return None

    node = limit_or_offset
    if isinstance(node, (exp.Limit, exp.Offset)):
        node = node.expression

    if isinstance(node, exp.Literal) and node.is_int:
        return int(node.this)

    try:
        return int(node.sql())
    except Exception:
        return None
