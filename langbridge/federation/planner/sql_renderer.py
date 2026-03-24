from collections.abc import Callable
from sqlglot import exp

from langbridge.federation.utils.sql import normalize_sql_dialect


ExpressionNormalizer = Callable[[exp.Expression], exp.Expression]


def render_local_stage_sql(
    expression: exp.Expression,
    *,
    stage_tables: dict[str, str],
    source_dialect: str,
    target_dialect: str,
) -> str:
    normalized_target = normalize_sql_dialect(target_dialect, default="duckdb")
    rewritten = rewrite_tables_to_stage_expression(expression, stage_tables=stage_tables)
    normalized = normalize_expression_for_dialect_boundary(
        rewritten,
        source_dialect=source_dialect,
        target_dialect=normalized_target,
    )
    return normalized.sql(dialect=normalized_target)


def rewrite_tables_to_stage_expression(
    expression: exp.Expression,
    *,
    stage_tables: dict[str, str],
) -> exp.Expression:
    alias_lookup = _build_table_alias_lookup(expression)

    def _replace(node: exp.Expression) -> exp.Expression:
        if isinstance(node, exp.Column):
            return _rewrite_column_for_stage(
                column=node,
                stage_tables=stage_tables,
                alias_lookup=alias_lookup,
            )
        if not isinstance(node, exp.Table):
            return node
        alias = node.alias_or_name
        stage_table = stage_tables.get(alias)
        if stage_table is None:
            return node
        return exp.table_(stage_table, alias=alias, quoted=False)

    return expression.copy().transform(_replace)


def normalize_expression_for_dialect_boundary(
    expression: exp.Expression,
    *,
    source_dialect: str,
    target_dialect: str,
) -> exp.Expression:
    normalized_source = normalize_sql_dialect(source_dialect)
    normalized_target = normalize_sql_dialect(target_dialect, default="duckdb")

    normalized = expression.copy()
    for normalizer in _TARGET_DIALECT_NORMALIZERS.get(normalized_target, ()):
        normalized = normalizer(normalized)
    for normalizer in _DIALECT_BOUNDARY_NORMALIZERS.get(
        (normalized_source, normalized_target),
        (),
    ):
        normalized = normalizer(normalized)
    return normalized


def _build_table_alias_lookup(expression: exp.Expression) -> dict[str, str]:
    candidate_aliases: dict[str, set[str]] = {}

    def _add(key: str | None, alias: str | None) -> None:
        if not key or not alias:
            return
        normalized_key = key.strip().lower()
        normalized_alias = alias.strip()
        if not normalized_key or not normalized_alias:
            return
        candidate_aliases.setdefault(normalized_key, set()).add(normalized_alias)

    for table in expression.find_all(exp.Table):
        alias = str(table.alias_or_name or "").strip()
        if not alias:
            continue

        table_name = str(table.name or "").strip()
        schema_name = str(table.db or "").strip()
        catalog_name = str(table.catalog or "").strip()

        _add(alias, alias)
        _add(table_name, alias)
        if schema_name and table_name:
            _add(f"{schema_name}.{table_name}", alias)
        if catalog_name and schema_name and table_name:
            _add(f"{catalog_name}.{schema_name}.{table_name}", alias)

    return {
        key: next(iter(aliases))
        for key, aliases in candidate_aliases.items()
        if len(aliases) == 1
    }


def _rewrite_column_for_stage(
    *,
    column: exp.Column,
    stage_tables: dict[str, str],
    alias_lookup: dict[str, str],
) -> exp.Column:
    table_name = str(column.table or "").strip()
    schema_name = str(column.db or "").strip()
    catalog_name = str(column.catalog or "").strip()

    resolved_alias: str | None = None
    candidates: list[str] = []
    if table_name:
        candidates.append(table_name)
    if schema_name and table_name:
        candidates.append(f"{schema_name}.{table_name}")
    if catalog_name and schema_name and table_name:
        candidates.append(f"{catalog_name}.{schema_name}.{table_name}")

    for candidate in candidates:
        normalized_candidate = candidate.strip().lower()
        alias = alias_lookup.get(normalized_candidate)
        if alias:
            resolved_alias = alias
            break

    if resolved_alias is None and table_name and table_name in stage_tables:
        resolved_alias = table_name

    rewritten = column.copy()
    if resolved_alias:
        rewritten.set("table", exp.Identifier(this=resolved_alias, quoted=False))
    rewritten.set("db", None)
    rewritten.set("catalog", None)
    return rewritten


def _normalize_postgres_duckdb_expression(expression: exp.Expression) -> exp.Expression:
    return expression.transform(_normalize_postgres_duckdb_node)


def _normalize_postgres_duckdb_node(node: exp.Expression) -> exp.Expression:
    if not isinstance(node, exp.Anonymous):
        return node

    normalizer = _POSTGRES_DUCKDB_FUNCTION_NORMALIZERS.get(
        str(node.name or "").strip().lower()
    )
    if normalizer is None:
        return node
    return normalizer(node)


def _normalize_trim_function(node: exp.Anonymous) -> exp.Expression:
    arguments = [argument.copy() for argument in (node.expressions or [])]
    if len(arguments) == 1:
        return exp.Trim(this=arguments[0])
    if len(arguments) == 2:
        return exp.Trim(this=arguments[0], expression=arguments[1])
    return node


_POSTGRES_DUCKDB_FUNCTION_NORMALIZERS: dict[str, Callable[[exp.Anonymous], exp.Expression]] = {
    "btrim": _normalize_trim_function,
}

_TARGET_DIALECT_NORMALIZERS: dict[str, tuple[ExpressionNormalizer, ...]] = {}

_DIALECT_BOUNDARY_NORMALIZERS: dict[tuple[str, str], tuple[ExpressionNormalizer, ...]] = {
    ("postgres", "duckdb"): (_normalize_postgres_duckdb_expression,),
}
