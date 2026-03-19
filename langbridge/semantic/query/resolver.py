import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from langbridge.semantic.errors import SemanticModelError
from langbridge.semantic.model import (
    DatasetFilter,
    Dimension,
    Measure,
    Metric,
    SemanticModel,
)


@dataclass(frozen=True)
class DimensionRef:
    dataset: str
    column: str
    expression: str
    data_type: Optional[str]
    alias: Optional[str]


@dataclass(frozen=True)
class MeasureRef:
    dataset: str
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
    dataset: str
    key: str
    condition: str


class SemanticModelResolver:
    def __init__(self, model: SemanticModel) -> None:
        self.model = model
        self._dimensions_by_key: Dict[str, Dimension] = {}
        self._measures_by_key: Dict[str, Measure] = {}
        self._metrics_by_key: Dict[str, Metric] = dict(model.metrics or {})
        self._filters_by_key: Dict[str, DatasetFilter] = {}
        self._dimensions_by_name: Dict[str, List[Tuple[str, Dimension]]] = {}
        self._measures_by_name: Dict[str, List[Tuple[str, Measure]]] = {}
        self._filters_by_name: Dict[str, List[Tuple[str, str, DatasetFilter]]] = {}
        self._dataset_keys: Set[str] = set(model.datasets.keys())
        self._datasets_by_compound: Dict[str, str] = {}
        self._build_indexes()
        self._logger = logging.getLogger(__name__)

    @property
    def dataset_keys(self) -> Set[str]:
        return set(self._dataset_keys)

    def resolve_dimension(self, member: str) -> DimensionRef:
        dataset, dimension = self._resolve_dimension(member)
        return DimensionRef(
            dataset=dataset,
            column=dimension.name,
            expression=dimension.expression or dimension.name,
            data_type=dimension.type,
            alias=dimension.alias,
        )

    def resolve_measure(self, member: str) -> MeasureRef:
        dataset, measure = self._resolve_measure(member)
        return MeasureRef(
            dataset=dataset,
            column=measure.name,
            expression=measure.expression or measure.name,
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
            self._logger.info("Resolving metric: %s", member)
            return self.resolve_metric(member)
        try:
            self._logger.info("Resolving measure: %s", member)
            return self.resolve_measure(member)
        except SemanticModelError:
            if member in self._metrics_by_key:
                return self.resolve_metric(member)
            raise

    def resolve_segment(self, segment: str) -> SegmentRef:
        dataset, key, dataset_filter = self._resolve_filter(segment)
        return SegmentRef(dataset=dataset, key=key, condition=dataset_filter.condition)

    def extract_datasets_from_expression(self, expression: str) -> Set[str]:
        datasets: Set[str] = set()
        for dataset in self._dataset_keys:
            pattern = rf"\b{re.escape(dataset)}\."
            if re.search(pattern, expression):
                datasets.add(dataset)
        return datasets

    def extract_tables_from_expression(self, expression: str) -> Set[str]:
        return self.extract_datasets_from_expression(expression)

    def _build_indexes(self) -> None:
        for dataset_key, dataset in self.model.datasets.items():
            candidates = [dataset.get_relation_name(dataset_key)]
            schema_relation = ".".join(
                part for part in [dataset.schema_name, dataset.get_relation_name(dataset_key)] if part
            )
            if schema_relation:
                candidates.append(schema_relation)
                if dataset.catalog_name:
                    candidates.append(f"{dataset.catalog_name}.{schema_relation}")
            for compound in candidates:
                if compound:
                    self._datasets_by_compound[compound] = dataset_key

            for dimension in dataset.dimensions or []:
                key = f"{dataset_key}.{dimension.name}"
                self._dimensions_by_key[key] = dimension
                self._dimensions_by_name.setdefault(dimension.name, []).append((dataset_key, dimension))

            for measure in dataset.measures or []:
                key = f"{dataset_key}.{measure.name}"
                self._measures_by_key[key] = measure
                self._measures_by_name.setdefault(measure.name, []).append((dataset_key, measure))

            for filter_key, dataset_filter in (dataset.filters or {}).items():
                key = f"{dataset_key}.{filter_key}"
                self._filters_by_key[key] = dataset_filter
                self._filters_by_name.setdefault(filter_key, []).append((dataset_key, filter_key, dataset_filter))

    def _resolve_compound_member(self, member: str) -> Tuple[str, str] | None:
        parts = member.split(".")
        if len(parts) < 3:
            return None
        for size in (3, 2):
            compound = ".".join(parts[:size])
            column = ".".join(parts[size:])
            dataset_key = self._datasets_by_compound.get(compound)
            if dataset_key and column:
                return dataset_key, column
        return None

    def _resolve_dimension(self, member: str) -> Tuple[str, Dimension]:
        self._logger.info("Resolving dimension: %s in dimensions: %s", member, self._dimensions_by_key.keys())
        if "." in member:
            dimension = self._dimensions_by_key.get(member)
            if dimension is None:
                compound = self._resolve_compound_member(member)
                if compound:
                    dataset_key, column = compound
                    compound_key = f"{dataset_key}.{column}"
                    dimension = self._dimensions_by_key.get(compound_key)
                    if dimension is not None:
                        return dataset_key, dimension
                raise SemanticModelError(f"Unknown dimension '{member}'.")
            dataset, _ = member.split(".", 1)
            return dataset, dimension

        matches = self._dimensions_by_name.get(member, [])
        if not matches:
            raise SemanticModelError(f"Unknown dimension '{member}'.")
        if len(matches) > 1:
            datasets = ", ".join(sorted(dataset for dataset, _ in matches))
            raise SemanticModelError(f"Ambiguous dimension '{member}'. Use dataset prefix. ({datasets})")
        dataset, dimension = matches[0]
        return dataset, dimension

    def _resolve_measure(self, member: str) -> Tuple[str, Measure]:
        self._logger.info("Resolving measure: %s in measures: %s", member, self._measures_by_key.keys())
        if "." in member:
            measure = self._measures_by_key.get(member)
            if measure is None:
                compound = self._resolve_compound_member(member)
                if compound:
                    dataset_key, column = compound
                    compound_key = f"{dataset_key}.{column}"
                    measure = self._measures_by_key.get(compound_key)
                    if measure is not None:
                        return dataset_key, measure
                raise SemanticModelError(f"Unknown measure '{member}'.")
            dataset, _ = member.split(".", 1)
            return dataset, measure

        matches = self._measures_by_name.get(member, [])
        if not matches:
            raise SemanticModelError(f"Unknown measure '{member}'.")
        if len(matches) > 1:
            datasets = ", ".join(sorted(dataset for dataset, _ in matches))
            raise SemanticModelError(f"Ambiguous measure '{member}'. Use dataset prefix. ({datasets})")
        dataset, measure = matches[0]
        return dataset, measure

    def _resolve_filter(self, segment: str) -> Tuple[str, str, DatasetFilter]:
        self._logger.info("Resolving filter: %s in filters: %s", segment, self._filters_by_key.keys())
        if "." in segment:
            dataset_filter = self._filters_by_key.get(segment)
            if dataset_filter is None:
                compound = self._resolve_compound_member(segment)
                if compound:
                    dataset_key, column = compound
                    compound_key = f"{dataset_key}.{column}"
                    dataset_filter = self._filters_by_key.get(compound_key)
                    if dataset_filter is not None:
                        return dataset_key, column, dataset_filter
                raise SemanticModelError(f"Unknown segment '{segment}'.")
            dataset, key = segment.split(".", 1)
            return dataset, key, dataset_filter

        matches = self._filters_by_name.get(segment, [])
        if not matches:
            raise SemanticModelError(f"Unknown segment '{segment}'.")
        if len(matches) > 1:
            datasets = ", ".join(sorted(dataset for dataset, _, _ in matches))
            raise SemanticModelError(f"Ambiguous segment '{segment}'. Use dataset prefix. ({datasets})")
        dataset, key, dataset_filter = matches[0]
        return dataset, key, dataset_filter
