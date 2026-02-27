import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from langbridge.packages.semantic.langbridge_semantic.errors import SemanticModelError
from langbridge.packages.semantic.langbridge_semantic.model import Dimension, Measure, Metric, SemanticModel, TableFilter


@dataclass(frozen=True)
class DimensionRef:
    table: str
    column: str
    expression: str
    data_type: Optional[str]
    alias: Optional[str]


@dataclass(frozen=True)
class MeasureRef:
    table: str
    column: str
    expression: str
    data_type: Optional[str]
    aggregation: Optional[str]

@dataclass(frozen=True)
class MetricRef:
    key: str
    expression: str


@dataclass(frozen=True)
class SegmentRef:
    table: str
    key: str
    condition: str


class SemanticModelResolver:
    def __init__(self, model: SemanticModel) -> None:
        self.model = model
        self._dimensions_by_key: Dict[str, Dimension] = {}
        self._measures_by_key: Dict[str, Measure] = {}
        self._metrics_by_key: Dict[str, Metric] = dict(model.metrics or {})
        self._filters_by_key: Dict[str, TableFilter] = {}
        self._dimensions_by_name: Dict[str, List[Tuple[str, Dimension]]] = {}
        self._measures_by_name: Dict[str, List[Tuple[str, Measure]]] = {}
        self._filters_by_name: Dict[str, List[Tuple[str, str, TableFilter]]] = {}
        self._table_keys: Set[str] = set(model.tables.keys())
        self._tables_by_compound: Dict[str, str] = {}
        self._build_indexes()
        self._logger = logging.getLogger(__name__)

    @property
    def table_keys(self) -> Set[str]:
        return set(self._table_keys)

    def resolve_dimension(self, member: str) -> DimensionRef:
        table, dimension = self._resolve_dimension(member)
        return DimensionRef(
            table=table,
            column=dimension.name,
            expression=dimension.expression,
            data_type=dimension.type,
            alias=dimension.alias,
        )

    def resolve_measure(self, member: str) -> MeasureRef:
        table, measure = self._resolve_measure(member)
        return MeasureRef(
            table=table,
            column=measure.name,
            expression=measure.expression,
            data_type=measure.type,
            aggregation=measure.aggregation,
        )

    def resolve_metric(self, member: str) -> MetricRef:
        metric = self._metrics_by_key.get(member)
        if metric is None:
            raise SemanticModelError(f"Unknown metric '{member}'.")
        return MetricRef(key=member, expression=metric.expression)

    def resolve_measure_or_metric(self, member: str) -> MeasureRef | MetricRef:
        if member in self._metrics_by_key:
            self._logger.info(f"Resolving metric: {member}")
            return self.resolve_metric(member)
        try:
            self._logger.info(f"Resolving measure: {member}")
            return self.resolve_measure(member)
        except SemanticModelError:
            if member in self._metrics_by_key:
                return self.resolve_metric(member)
            raise

    def resolve_segment(self, segment: str) -> SegmentRef:
        table, key, table_filter = self._resolve_filter(segment)
        return SegmentRef(table=table, key=key, condition=table_filter.condition)

    def extract_tables_from_expression(self, expression: str) -> Set[str]:
        tables: Set[str] = set()
        for table in self._table_keys:
            pattern = rf"\b{re.escape(table)}\."
            if re.search(pattern, expression):
                tables.add(table)
        return tables

    def _build_indexes(self) -> None:
        for table_key, table in self.model.tables.items():
            compound = f"{table.schema}.{table.name}" if table.schema else table.name
            if compound:
                self._tables_by_compound[compound] = table_key
            for dimension in table.dimensions or []:
                key = f"{table_key}.{dimension.name}"
                self._dimensions_by_key[key] = dimension
                self._dimensions_by_name.setdefault(dimension.name, []).append((table_key, dimension))

            for measure in table.measures or []:
                key = f"{table_key}.{measure.name}"
                self._measures_by_key[key] = measure
                self._measures_by_name.setdefault(measure.name, []).append((table_key, measure))

            for filter_key, table_filter in (table.filters or {}).items():
                key = f"{table_key}.{filter_key}"
                self._filters_by_key[key] = table_filter
                self._filters_by_name.setdefault(filter_key, []).append(
                    (table_key, filter_key, table_filter)
                )

    def _resolve_compound_member(self, member: str) -> Tuple[str, str] | None:
        parts = member.split(".")
        if len(parts) < 3:
            return None
        compound = ".".join(parts[:2])
        column = ".".join(parts[2:])
        table_key = self._tables_by_compound.get(compound)
        if not table_key or not column:
            return None
        return table_key, column

    def _resolve_dimension(self, member: str) -> Tuple[str, Dimension]:
        self._logger.info(f"Resolving dimension: {member} in dimensions: {self._dimensions_by_key.keys()}")
        if "." in member:
            dimension = self._dimensions_by_key.get(member)
            if dimension is None:
                compound = self._resolve_compound_member(member)
                if compound:
                    table_key, column = compound
                    compound_key = f"{table_key}.{column}"
                    dimension = self._dimensions_by_key.get(compound_key)
                    if dimension is not None:
                        return table_key, dimension
                raise SemanticModelError(f"Unknown dimension '{member}'.")
            table, _ = member.split(".", 1)
            return table, dimension

        matches = self._dimensions_by_name.get(member, [])
        if not matches:
            raise SemanticModelError(f"Unknown dimension '{member}'.")
        if len(matches) > 1:
            tables = ", ".join(sorted(table for table, _ in matches))
            raise SemanticModelError(f"Ambiguous dimension '{member}'. Use table prefix. ({tables})")
        table, dimension = matches[0]
        return table, dimension

    def _resolve_measure(self, member: str) -> Tuple[str, Measure]:
        self._logger.info(f"Resolving measure: {member} in measures: {self._measures_by_key.keys()}")
        if "." in member:
            measure = self._measures_by_key.get(member)
            if measure is None:
                compound = self._resolve_compound_member(member)
                if compound:
                    table_key, column = compound
                    compound_key = f"{table_key}.{column}"
                    measure = self._measures_by_key.get(compound_key)
                    if measure is not None:
                        return table_key, measure
                raise SemanticModelError(f"Unknown measure '{member}'.")
            table, _ = member.split(".", 1)
            return table, measure

        matches = self._measures_by_name.get(member, [])
        if not matches:
            raise SemanticModelError(f"Unknown measure '{member}'.")
        if len(matches) > 1:
            tables = ", ".join(sorted(table for table, _ in matches))
            raise SemanticModelError(f"Ambiguous measure '{member}'. Use table prefix. ({tables})")
        table, measure = matches[0]
        return table, measure

    def _resolve_filter(self, segment: str) -> Tuple[str, str, TableFilter]:
        self._logger.info(f"Resolving filter: {segment} in filters: {self._filters_by_key.keys()}")
        if "." in segment:
            table_filter = self._filters_by_key.get(segment)
            if table_filter is None:
                compound = self._resolve_compound_member(segment)
                if compound:
                    table_key, column = compound
                    compound_key = f"{table_key}.{column}"
                    table_filter = self._filters_by_key.get(compound_key)
                    if table_filter is not None:
                        return table_key, column, table_filter
                raise SemanticModelError(f"Unknown segment '{segment}'.")
            table, key = segment.split(".", 1)
            return table, key, table_filter

        matches = self._filters_by_name.get(segment, [])
        if not matches:
            raise SemanticModelError(f"Unknown segment '{segment}'.")
        if len(matches) > 1:
            tables = ", ".join(sorted(table for table, _, _ in matches))
            raise SemanticModelError(f"Ambiguous segment '{segment}'. Use table prefix. ({tables})")
        table, key, table_filter = matches[0]
        return table, key, table_filter
