"""Physical execution of query plans for the LangBridge experimental engine."""



from typing import Any, Dict, List, Mapping, Sequence, Tuple

from .datasource import DataSourceRegistry, TableHandle
from .exceptions import QueryExecutionError
from .model import ColumnRef, Literal, Predicate, PredicateOperand, SelectItem, Wildcard
from .planner import FilterNode, JoinNode, PlanNode, ProjectionNode, ScanNode


class TableData:
    """Internal representation of table data used during plan execution."""

    def __init__(self, columns: Sequence[str], rows: Sequence[Mapping[str, Any]]):
        self.columns = list(columns)
        self.rows = [dict(row) for row in rows]


class QueryExecutor:
    """Execute a query plan against registered data sources."""

    def __init__(self, registry: DataSourceRegistry):
        self._registry = registry

    def execute(self, plan: ProjectionNode) -> "QueryResult":
        data = self._execute_node(plan.input)
        return self._project(data, plan.select_items)

    def _execute_node(self, node: PlanNode) -> TableData:
        if isinstance(node, ScanNode):
            return self._execute_scan(node)
        if isinstance(node, JoinNode):
            return self._execute_join(node)
        if isinstance(node, FilterNode):
            input_data = self._execute_node(node.input)
            return self._apply_filters(input_data, node.predicates)
        if isinstance(node, ProjectionNode):
            return self._execute_node(node.input)
        raise QueryExecutionError(f"Unsupported plan node {type(node).__name__}")

    def _execute_scan(self, node: ScanNode) -> TableData:
        source = self._registry.get(node.table.source)
        raw_table = source.fetch_table(TableHandle(node.table.path))
        columns, rows = raw_table.materialize()
        qualified_columns = [f"{node.table.alias}.{column}" for column in columns]
        qualified_rows: List[Dict[str, Any]] = []
        for row in rows:
            qualified_rows.append(
                {
                    f"{node.table.alias}.{column}": row.get(column)
                    for column in columns
                }
            )
        return TableData(columns=qualified_columns, rows=qualified_rows)

    def _execute_join(self, node: JoinNode) -> TableData:
        if node.join_type != "INNER":
            raise QueryExecutionError(f"Unsupported join type {node.join_type!r}")

        left_data = self._execute_node(node.left)
        right_data = self._execute_node(node.right)

        if not node.predicates:
            return self._cross_join(left_data, right_data)

        left_columns = set(left_data.columns)
        right_columns = set(right_data.columns)
        left_keys: List[str] = []
        right_keys: List[str] = []
        for predicate in node.predicates:
            if not isinstance(predicate.left, ColumnRef) or not isinstance(predicate.right, ColumnRef):
                raise QueryExecutionError("Join predicates must compare column references")
            left_key = f"{predicate.left.table_alias}.{predicate.left.column}"
            right_key = f"{predicate.right.table_alias}.{predicate.right.column}"

            if left_key in left_columns and right_key in right_columns:
                left_keys.append(left_key)
                right_keys.append(right_key)
            elif left_key in right_columns and right_key in left_columns:
                left_keys.append(right_key)
                right_keys.append(left_key)
            else:
                raise QueryExecutionError(
                    "Join predicate must reference columns from both sides of the join"
                )

        right_index: Dict[Tuple[Any, ...], List[Dict[str, Any]]] = {}
        for row in right_data.rows:
            key = tuple(row.get(column) for column in right_keys)
            right_index.setdefault(key, []).append(row)

        joined_columns = list(left_data.columns)
        for column in right_data.columns:
            if column not in joined_columns:
                joined_columns.append(column)

        joined_rows: List[Dict[str, Any]] = []
        for left_row in left_data.rows:
            key = tuple(left_row.get(column) for column in left_keys)
            matching_rows = right_index.get(key, [])
            for right_row in matching_rows:
                combined = dict(left_row)
                combined.update(right_row)
                joined_rows.append(combined)

        return TableData(columns=joined_columns, rows=joined_rows)

    def _cross_join(self, left: TableData, right: TableData) -> TableData:
        columns = list(left.columns)
        for column in right.columns:
            if column not in columns:
                columns.append(column)

        rows: List[Dict[str, Any]] = []
        for lrow in left.rows:
            for rrow in right.rows:
                combined = dict(lrow)
                combined.update(rrow)
                rows.append(combined)

        return TableData(columns=columns, rows=rows)

    def _apply_filters(self, data: TableData, predicates: Sequence[Predicate]) -> TableData:
        filtered_rows = [
            row for row in data.rows if all(self._evaluate_predicate(row, predicate) for predicate in predicates)
        ]
        return TableData(columns=list(data.columns), rows=filtered_rows)

    def _evaluate_predicate(self, row: Mapping[str, Any], predicate: Predicate) -> bool:
        left = self._resolve_operand(row, predicate.left)
        right = self._resolve_operand(row, predicate.right)
        operator = predicate.operator

        if operator in ("=", "=="):
            return left == right
        if operator in ("<>", "!="):
            return left != right
        if operator == "<":
            return left < right
        if operator == ">":
            return left > right
        if operator == "<=":
            return left <= right
        if operator == ">=":
            return left >= right

        raise QueryExecutionError(f"Unsupported operator {operator!r}")

    def _resolve_operand(self, row: Mapping[str, Any], operand: PredicateOperand) -> Any:
        if isinstance(operand, ColumnRef):
            key = f"{operand.table_alias}.{operand.column}"
            if key not in row:
                raise QueryExecutionError(f"Column {key!r} not available in the current scope")
            return row[key]
        if isinstance(operand, Literal):
            return operand.value
        raise QueryExecutionError(f"Unsupported operand type {type(operand).__name__}")

    def _project(self, data: TableData, select_items: Sequence[SelectItem]) -> "QueryResult":
        if not data.columns and not data.rows and not select_items:
            return QueryResult(columns=[], rows=[])

        column_mappings: List[Tuple[str, str]] = []
        seen_output_names: set[str] = set()

        def ensure_unique(name: str, fallback: str) -> str:
            candidate = name or fallback
            if candidate in seen_output_names:
                suffix = 1
                base = candidate
                while f"{base}_{suffix}" in seen_output_names:
                    suffix += 1
                candidate = f"{base}_{suffix}"
            seen_output_names.add(candidate)
            return candidate

        for item in select_items:
            if isinstance(item.value, Wildcard):
                if item.value.table_alias:
                    prefix = f"{item.value.table_alias}."
                    matched_columns = [col for col in data.columns if col.startswith(prefix)]
                else:
                    matched_columns = list(data.columns)

                for column in matched_columns:
                    base_name = column.split(".", 1)[-1]
                    output_name = ensure_unique(base_name, column)
                    column_mappings.append((output_name, column))
                continue

            column_ref = item.value
            column_key = f"{column_ref.table_alias}.{column_ref.column}"
            if column_key not in data.columns:
                raise QueryExecutionError(f"Column {column_key!r} not present in query result")

            preferred_name = item.alias or column_ref.column
            output_name = ensure_unique(preferred_name, column_key)
            column_mappings.append((output_name, column_key))

        projected_rows: List[Tuple[Any, ...]] = []
        for row in data.rows:
            projected_rows.append(tuple(row.get(source) for _, source in column_mappings))

        output_columns = [name for name, _ in column_mappings]
        return QueryResult(columns=output_columns, rows=projected_rows)


class QueryResult:
    """Structured query results."""

    def __init__(self, columns: Sequence[str], rows: Sequence[Tuple[Any, ...]]):
        self.columns = list(columns)
        self.rows = list(rows)

    def to_dicts(self) -> List[Dict[str, Any]]:
        """Return the results as a list of dictionaries keyed by column name."""
        return [dict(zip(self.columns, row)) for row in self.rows]

    def to_rows(self) -> List[Tuple[Any, ...]]:
        """Return results as a list of positional tuples."""
        return list(self.rows)


__all__ = [
    "QueryExecutor",
    "QueryResult",
    "TableData",
]
