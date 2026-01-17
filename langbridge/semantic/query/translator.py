import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

import yaml

from semantic.errors import SemanticModelError, SemanticQueryError
from .join_planner import JoinPlanner
from semantic.model import SemanticModel
from .query_model import FilterItem, SemanticQuery
from .resolver import DimensionRef, MeasureRef, MetricRef, SemanticModelResolver, SegmentRef
from .tsql import build_date_range_condition, date_trunc, format_literal, quote_compound, quote_identifier


@dataclass(frozen=True)
class TimeDimensionRef:
    dimension: DimensionRef
    granularity: Optional[str]
    date_range: Optional[Any]


@dataclass(frozen=True)
class FilterTarget:
    kind: str
    expression: str
    data_type: Optional[str]
    tables: Set[str]


@dataclass(frozen=True)
class OrderItem:
    member: str
    direction: str


class TsqlSemanticTranslator:
    def __init__(self):
        self._logger = logging.getLogger(__name__)

    def translate(self, query: SemanticQuery | Dict[str, Any], model: SemanticModel) -> str:
        if isinstance(query, SemanticQuery):
            parsed = query
        else:
            parsed = SemanticQuery.model_validate(query)

        resolver = SemanticModelResolver(model)
        dimensions = [resolver.resolve_dimension(member) for member in parsed.dimensions]
        time_dimensions = [
            TimeDimensionRef(
                dimension=resolver.resolve_dimension(item.dimension),
                granularity=item.granularity,
                date_range=item.date_range,
            )
            for item in parsed.time_dimensions
        ]

        measures: List[MeasureRef] = []
        metrics: List[MetricRef] = []
        for member in parsed.measures:
            resolved = resolver.resolve_measure_or_metric(member)
            if isinstance(resolved, MetricRef):
                metrics.append(resolved)
            else:
                measures.append(resolved)

        filter_targets: List[FilterTarget] = []
        for item in parsed.filters:
            filter_targets.append(self._resolve_filter_target(resolver, item))

        segments = [resolver.resolve_segment(segment) for segment in parsed.segments]

        required_tables = self._collect_required_tables(
            resolver,
            dimensions,
            time_dimensions,
            measures,
            metrics,
            filter_targets,
            segments,
        )
        base_table = self._choose_base_table(
            dimensions,
            time_dimensions,
            measures,
            metrics,
            filter_targets,
            segments,
        )
        if base_table not in required_tables:
            required_tables.add(base_table)

        join_steps = JoinPlanner(model.relationships).plan(base_table, required_tables)
        alias_map = self._build_alias_map(base_table, join_steps)

        select_clauses, group_by_expressions, order_aliases = self._build_selects(
            alias_map, dimensions, time_dimensions, measures, metrics, resolver
        )
        where_conditions = self._build_where_conditions(
            alias_map, filter_targets, time_dimensions, segments
        )
        having_conditions = self._build_having_conditions(alias_map, filter_targets)

        order_items = self._normalize_order(parsed.order)
        order_clause = self._build_order_clause(
            order_items,
            order_aliases,
            alias_map,
            resolver,
            dimensions,
            time_dimensions,
            measures,
            metrics,
        )

        sql_parts: List[str] = []
        sql_parts.append("SELECT")
        sql_parts.append(self._indent(",\n".join(select_clauses)))
        sql_parts.append(self._render_from(model, base_table, alias_map, join_steps))

        if where_conditions:
            sql_parts.append("WHERE")
            sql_parts.append(self._indent(" AND\n".join(where_conditions)))

        if group_by_expressions:
            sql_parts.append("GROUP BY")
            sql_parts.append(self._indent(",\n".join(group_by_expressions)))

        if having_conditions:
            sql_parts.append("HAVING")
            sql_parts.append(self._indent(" AND\n".join(having_conditions)))

        if order_clause:
            sql_parts.append(order_clause)

        limit_clause = self._build_limit_clause(parsed.limit, parsed.offset, bool(order_clause))
        if limit_clause:
            sql_parts.append(limit_clause)

        return "\n".join(sql_parts).strip() + ";"

    def load_semantic_model(self, yaml_text: str) -> SemanticModel:
        payload = yaml.safe_load(yaml_text)
        return SemanticModel.model_validate(payload)

    def _collect_required_tables(
        self,
        resolver: SemanticModelResolver,
        dimensions: Sequence[DimensionRef],
        time_dimensions: Sequence[TimeDimensionRef],
        measures: Sequence[MeasureRef],
        metrics: Sequence[MetricRef],
        filter_targets: Sequence[FilterTarget],
        segments: Sequence[SegmentRef],
    ) -> Set[str]:
        required_tables: Set[str] = set()

        for dimension in dimensions:
            required_tables.add(dimension.table)
        for time_dimension in time_dimensions:
            required_tables.add(time_dimension.dimension.table)
        for measure in measures:
            required_tables.add(measure.table)
        for metric in metrics:
            required_tables.update(resolver.extract_tables_from_expression(metric.expression))
        for target in filter_targets:
            required_tables.update(target.tables)
        for segment in segments:
            required_tables.add(segment.table)

        return required_tables

    def _choose_base_table(
        self,
        dimensions: Sequence[DimensionRef],
        time_dimensions: Sequence[TimeDimensionRef],
        measures: Sequence[MeasureRef],
        metrics: Sequence[MetricRef],
        filter_targets: Sequence[FilterTarget],
        segments: Sequence[SegmentRef],
    ) -> str:
        if measures:
            return measures[0].table
        if metrics:
            for table in self._tables_from_expression(metrics[0].key):
                return table
        if time_dimensions:
            return time_dimensions[0].dimension.table
        if dimensions:
            return dimensions[0].table
        if filter_targets:
            return next(iter(filter_targets[0].tables))
        if segments:
            return segments[0].table
        raise SemanticQueryError(f"Semantic query did not reference any tables in {dimensions}, {time_dimensions}, {measures}, {metrics}, {filter_targets}, {segments}.")

    def _tables_from_expression(self, expression: str) -> List[str]:
        matches = re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\.", expression)
        return matches

    def _build_alias_map(self, base_table: str, join_steps: Sequence[Any]) -> Dict[str, str]:
        alias_map: Dict[str, str] = {base_table: "t0"}
        counter = 1
        for step in join_steps:
            if step.right_table not in alias_map:
                alias_map[step.right_table] = f"t{counter}"
                counter += 1
            if step.left_table not in alias_map:
                alias_map[step.left_table] = f"t{counter}"
                counter += 1
        return alias_map

    def _build_selects(
        self,
        alias_map: Dict[str, str],
        dimensions: Sequence[DimensionRef],
        time_dimensions: Sequence[TimeDimensionRef],
        measures: Sequence[MeasureRef],
        metrics: Sequence[MetricRef],
        resolver: SemanticModelResolver,
    ) -> Tuple[List[str], List[str], Dict[str, str]]:
        select_clauses: List[str] = []
        group_by_expressions: List[str] = []
        order_aliases: Dict[str, str] = {}

        for dimension in dimensions:
            expr = self._column_expression(alias_map, dimension.table, dimension.column)
            alias = self._alias_for_member(f"{dimension.table}.{dimension.column}")
            select_clauses.append(f"{expr} AS {quote_identifier(alias)}")
            group_by_expressions.append(expr)
            order_aliases[alias] = alias
            order_aliases[f"{dimension.table}.{dimension.column}"] = alias

        for time_dimension in time_dimensions:
            base_expr = self._column_expression(
                alias_map,
                time_dimension.dimension.table,
                time_dimension.dimension.column,
            )
            expr = base_expr
            if time_dimension.granularity:
                expr = date_trunc(time_dimension.granularity, base_expr)
            alias = self._alias_for_time_dimension(
                time_dimension.dimension.table,
                time_dimension.dimension.column,
                time_dimension.granularity,
            )
            select_clauses.append(f"{expr} AS {quote_identifier(alias)}")
            group_by_expressions.append(expr)
            order_aliases[alias] = alias
            order_aliases[f"{time_dimension.dimension.table}.{time_dimension.dimension.column}"] = alias
            if time_dimension.granularity:
                order_aliases[
                    f"{time_dimension.dimension.table}.{time_dimension.dimension.column}.{time_dimension.granularity}"
                ] = alias

        for measure in measures:
            expr = self._measure_expression(alias_map, measure)
            alias = self._alias_for_member(f"{measure.table}.{measure.column}")
            select_clauses.append(f"{expr} AS {quote_identifier(alias)}")
            order_aliases[alias] = alias
            order_aliases[f"{measure.table}.{measure.column}"] = alias

        for metric in metrics:
            expr = self._replace_table_refs(metric.expression, alias_map)
            alias = self._alias_for_member(metric.key)
            select_clauses.append(f"{expr} AS {quote_identifier(alias)}")
            order_aliases[alias] = alias
            order_aliases[metric.key] = alias

        if not select_clauses:
            raise SemanticQueryError("Semantic query did not include any dimensions, measures, or metrics.")

        return select_clauses, group_by_expressions, order_aliases

    def _build_where_conditions(
        self,
        alias_map: Dict[str, str],
        filter_targets: Sequence[FilterTarget],
        time_dimensions: Sequence[TimeDimensionRef],
        segments: Sequence[SegmentRef],
    ) -> List[str]:
        conditions: List[str] = []
        for target in filter_targets:
            if target.kind == "measure" or target.kind == "metric":
                continue
            conditions.append(self._replace_table_refs(target.expression, alias_map))

        for time_dimension in time_dimensions:
            if not time_dimension.date_range:
                continue
            column_expr = self._column_expression(
                alias_map,
                time_dimension.dimension.table,
                time_dimension.dimension.column,
            )
            conditions.append(
                build_date_range_condition(
                    column_expr,
                    time_dimension.date_range,
                    time_dimension.dimension.data_type,
                )
            )

        for segment in segments:
            condition = self._replace_table_refs(segment.condition, alias_map)
            conditions.append(condition)

        return conditions

    def _build_having_conditions(
        self,
        alias_map: Dict[str, str],
        filter_targets: Sequence[FilterTarget],
    ) -> List[str]:
        conditions: List[str] = []
        for target in filter_targets:
            if target.kind in {"measure", "metric"}:
                conditions.append(self._replace_table_refs(target.expression, alias_map))
        return conditions

    def _build_order_clause(
        self,
        order_items: Sequence[OrderItem],
        order_aliases: Dict[str, str],
        alias_map: Dict[str, str],
        resolver: SemanticModelResolver,
        dimensions: Sequence[DimensionRef],
        time_dimensions: Sequence[TimeDimensionRef],
        measures: Sequence[MeasureRef],
        metrics: Sequence[MetricRef],
    ) -> str:
        if not order_items:
            return ""

        clauses: List[str] = []
        for item in order_items:
            key = item.member
            alias = order_aliases.get(key)
            if alias:
                clauses.append(f"{quote_identifier(alias)} {item.direction}")
                continue

            resolved = self._resolve_order_member(
                key, alias_map, resolver, dimensions, time_dimensions, measures, metrics
            )
            clauses.append(f"{resolved} {item.direction}")

        if not clauses:
            return ""
        return "ORDER BY " + ", ".join(clauses)

    def _resolve_order_member(
        self,
        member: str,
        alias_map: Dict[str, str],
        resolver: SemanticModelResolver,
        dimensions: Sequence[DimensionRef],
        time_dimensions: Sequence[TimeDimensionRef],
        measures: Sequence[MeasureRef],
        metrics: Sequence[MetricRef],
    ) -> str:
        for time_dimension in time_dimensions:
            if member == f"{time_dimension.dimension.table}.{time_dimension.dimension.column}":
                expr = self._column_expression(
                    alias_map,
                    time_dimension.dimension.table,
                    time_dimension.dimension.column,
                )
                if time_dimension.granularity:
                    return date_trunc(time_dimension.granularity, expr)
                return expr

        try:
            dimension = resolver.resolve_dimension(member)
            return self._column_expression(alias_map, dimension.table, dimension.column)
        except SemanticModelError:
            pass

        try:
            measure = resolver.resolve_measure(member)
            return self._measure_expression(alias_map, measure)
        except SemanticModelError:
            pass

        if member in {metric.key for metric in metrics}:
            metric = next(metric for metric in metrics if metric.key == member)
            return self._replace_table_refs(metric.expression, alias_map)

        raise SemanticQueryError(f"Unable to resolve order member '{member}'.")

    def _build_limit_clause(self, limit: Optional[int], offset: Optional[int], has_order: bool) -> str:
        if limit is None and offset is None:
            return ""

        safe_limit = limit if limit is not None else 2147483647
        safe_offset = offset or 0
        if not has_order:
            return f"ORDER BY (SELECT 1)\nOFFSET {safe_offset} ROWS FETCH NEXT {safe_limit} ROWS ONLY"
        return f"OFFSET {safe_offset} ROWS FETCH NEXT {safe_limit} ROWS ONLY"

    def _render_from(
        self,
        model: SemanticModel,
        base_table: str,
        alias_map: Dict[str, str],
        join_steps: Sequence[Any],
    ) -> str:
        base_ref = self._table_ref(model, base_table)
        base_alias = alias_map[base_table]
        lines = [f"FROM {base_ref} AS {base_alias}"]

        for step in join_steps:
            right_ref = self._table_ref(model, step.right_table)
            right_alias = alias_map[step.right_table]
            join_on = self._replace_table_refs(step.relationship.join_on, alias_map)
            join_type = self._join_type(step.relationship.type)
            lines.append(f"{join_type} JOIN {right_ref} AS {right_alias} ON {join_on}")

        return "\n".join(lines)

    def _resolve_filter_target(self, resolver: SemanticModelResolver, item: FilterItem) -> FilterTarget:
        member = item.member or item.dimension or item.measure or item.time_dimension
        if not member:
            raise SemanticQueryError("Filter is missing member information.")

        operator = item.operator.strip().lower()
        values = item.values or []

        if item.dimension or item.time_dimension:
            dimension = resolver.resolve_dimension(member)
            expr = self._column_expression({}, dimension.table, dimension.column, allow_placeholder=True)
            sql = self._build_filter_expression(expr, operator, values, dimension.data_type)
            return FilterTarget(kind="dimension", expression=sql, data_type=dimension.data_type, tables={dimension.table})

        if item.measure:
            resolved = resolver.resolve_measure_or_metric(member)
            if isinstance(resolved, MetricRef):
                expr = resolved.expression
                sql = self._build_filter_expression(expr, operator, values, None)
                return FilterTarget(kind="metric", expression=sql, data_type=None, tables=resolver.extract_tables_from_expression(expr))
            expr = self._measure_expression({}, resolved, allow_placeholder=True)
            sql = self._build_filter_expression(expr, operator, values, resolved.data_type)
            return FilterTarget(kind="measure", expression=sql, data_type=resolved.data_type, tables={resolved.table})

        if member in (resolver.model.metrics or {}):
            metric = resolver.resolve_metric(member)
            expr = metric.expression
            sql = self._build_filter_expression(expr, operator, values, None)
            return FilterTarget(kind="metric", expression=sql, data_type=None, tables=resolver.extract_tables_from_expression(expr))

        try:
            dimension = resolver.resolve_dimension(member)
            expr = self._column_expression({}, dimension.table, dimension.column, allow_placeholder=True)
            sql = self._build_filter_expression(expr, operator, values, dimension.data_type)
            return FilterTarget(kind="dimension", expression=sql, data_type=dimension.data_type, tables={dimension.table})
        except SemanticModelError:
            pass

        resolved = resolver.resolve_measure_or_metric(member)
        if isinstance(resolved, MetricRef):
            expr = resolved.expression
            sql = self._build_filter_expression(expr, operator, values, None)
            return FilterTarget(kind="metric", expression=sql, data_type=None, tables=resolver.extract_tables_from_expression(expr))
        expr = self._measure_expression({}, resolved, allow_placeholder=True)
        sql = self._build_filter_expression(expr, operator, values, resolved.data_type)
        return FilterTarget(kind="measure", expression=sql, data_type=resolved.data_type, tables={resolved.table})

    def _build_filter_expression(
        self, expression: str, operator: str, values: Sequence[Any], data_type: Optional[str]
    ) -> str:
        op = operator.strip().lower()
        formatted_values = [format_literal(value, data_type) for value in values]

        if op in {"equals", "equal", "eq"}:
            if len(formatted_values) == 1:
                return f"{expression} = {formatted_values[0]}"
            return f"{expression} IN ({', '.join(formatted_values)})"
        if op in {"notequals", "not_equals", "ne"}:
            if len(formatted_values) == 1:
                return f"{expression} <> {formatted_values[0]}"
            return f"{expression} NOT IN ({', '.join(formatted_values)})"
        if op == "contains":
            return f"{expression} LIKE {format_literal(f'%{values[0]}%', None)}"
        if op == "notcontains":
            return f"{expression} NOT LIKE {format_literal(f'%{values[0]}%', None)}"
        if op == "startswith":
            return f"{expression} LIKE {format_literal(f'{values[0]}%', None)}"
        if op == "endswith":
            return f"{expression} LIKE {format_literal(f'%{values[0]}', None)}"
        if op in {"gt", "greater"}:
            return f"{expression} > {formatted_values[0]}"
        if op in {"gte", "gteq", "greater_or_equal"}:
            return f"{expression} >= {formatted_values[0]}"
        if op in {"lt", "less"}:
            return f"{expression} < {formatted_values[0]}"
        if op in {"lte", "lteq", "less_or_equal"}:
            return f"{expression} <= {formatted_values[0]}"
        if op == "beforedate":
            return f"{expression} < {formatted_values[0]}"
        if op == "afterdate":
            return f"{expression} > {formatted_values[0]}"
        if op == "indaterange":
            if len(values) == 1:
                date_range = values[0]
            else:
                date_range = list(values)
            return build_date_range_condition(expression, date_range, data_type)
        if op == "notindaterange":
            if len(values) == 1:
                date_range = values[0]
            else:
                date_range = list(values)
            return f"NOT ({build_date_range_condition(expression, date_range, data_type)})"
        if op == "set":
            return f"{expression} IS NOT NULL"
        if op == "notset":
            return f"{expression} IS NULL"
        if op == "in":
            return f"{expression} IN ({', '.join(formatted_values)})"
        if op == "notin":
            return f"{expression} NOT IN ({', '.join(formatted_values)})"

        raise SemanticQueryError(f"Unsupported filter operator '{operator}'.")

    def _measure_expression(
        self, alias_map: Dict[str, str], measure: MeasureRef, allow_placeholder: bool = False
    ) -> str:
        column_expr = self._column_expression(
            alias_map,
            measure.table,
            measure.column,
            allow_placeholder=allow_placeholder,
        )
        aggregation = (measure.aggregation or "").strip().lower()
        if not aggregation:
            aggregation = "sum" if (measure.data_type or "").lower() in {"integer", "decimal", "float", "number"} else "count"

        if aggregation in {"count_distinct", "countdistinct"}:
            return f"COUNT(DISTINCT {column_expr})"
        if aggregation == "count":
            return f"COUNT({column_expr})"
        return f"{aggregation.upper()}({column_expr})"

    def _column_expression(
        self,
        alias_map: Dict[str, str],
        table: str,
        column: str,
        allow_placeholder: bool = False,
    ) -> str:
        if not alias_map:
            if not allow_placeholder:
                raise SemanticQueryError("Column expression requested before aliases are available.")
            return f"{table}.{quote_identifier(column)}"
        alias = alias_map[table]
        return f"{alias}.{quote_identifier(column)}"

    def _replace_table_refs(self, expression: str, alias_map: Dict[str, str]) -> str:
        updated = expression
        for table, alias in alias_map.items():
            updated = re.sub(rf"\b{re.escape(table)}\.", f"{alias}.", updated)
        return updated

    def _table_ref(self, model: SemanticModel, table_key: str) -> str:
        table = model.tables.get(table_key)
        if table is None:
            raise SemanticQueryError(f"Unknown table '{table_key}'.")
        if table.schema:
            return quote_compound(f"{table.schema}.{table.name}")
        return quote_identifier(table.name)

    def _alias_for_member(self, member: str) -> str:
        alias = member.replace(".", "__").replace(" ", "_")
        return re.sub(r"[^A-Za-z0-9_]+", "_", alias)

    def _alias_for_time_dimension(self, table: str, column: str, granularity: Optional[str]) -> str:
        base = self._alias_for_member(f"{table}.{column}")
        if not granularity:
            return base
        return f"{base}_{granularity}"

    def _normalize_order(self, order: Any) -> List[OrderItem]:
        if order is None:
            return []

        items: List[OrderItem] = []
        if isinstance(order, dict):
            for key, direction in order.items():
                items.append(OrderItem(member=key, direction=self._normalize_direction(direction)))
            return items

        if isinstance(order, list):
            for entry in order:
                if isinstance(entry, dict):
                    for key, direction in entry.items():
                        items.append(OrderItem(member=key, direction=self._normalize_direction(direction)))
                elif isinstance(entry, (list, tuple)) and len(entry) == 2:
                    items.append(OrderItem(member=str(entry[0]), direction=self._normalize_direction(entry[1])))
            return items

        raise SemanticQueryError("Unsupported order format.")

    def _normalize_direction(self, direction: Any) -> str:
        value = str(direction or "asc").strip().lower()
        return "DESC" if value == "desc" else "ASC"

    def _join_type(self, relationship_type: Optional[str]) -> str:
        if relationship_type in {"one_to_many", "many_to_one", "one_to_one"}:
            return "LEFT"
        return "INNER"

    def _indent(self, text: str, spaces: int = 2) -> str:
        padding = " " * spaces
        return "\n".join(f"{padding}{line}" for line in text.splitlines())
