"""
Helpers to enrich semantic models with token lookup registries.

The resolved structure makes it easier to map natural language mentions to
canonical tables, columns, filters, and metrics defined in the semantic model.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from semantic import SemanticModel


@dataclass
class ResolvedModel:
    """
    Semantic model together with generated lookup indexes.
    """

    model: SemanticModel
    table_by_token: Dict[str, str]
    column_by_token: Dict[str, Tuple[str, str]]
    filter_by_token: Dict[str, Tuple[str, str]]
    metric_by_token: Dict[str, str]


def _add_token(mapping: Dict[str, str], token: Optional[str], value: str) -> None:
    if not token:
        return
    mapping[token.lower()] = value


def _add_token_pair(mapping: Dict[str, Tuple[str, str]], token: Optional[str], table: str, column: str) -> None:
    if not token:
        return
    mapping[token.lower()] = (table, column)


def _explode_synonyms(names: List[Optional[str]]) -> List[str]:
    out: List[str] = []
    for name in names:
        if not name:
            continue
        out.append(name)
        if "," in name:
            out.extend([part.strip() for part in name.split(",")])
    return out


def build_resolved_model(model: SemanticModel) -> ResolvedModel:
    """
    Generate lookup registries for a semantic model.
    """

    table_by_token: Dict[str, str] = {}
    column_by_token: Dict[str, Tuple[str, str]] = {}
    filter_by_token: Dict[str, Tuple[str, str]] = {}
    metric_by_token: Dict[str, str] = {}

    for table_name, table in model.tables.items():
        _add_token(table_by_token, table_name, table_name)
        if table.synonyms:
            for synonym in table.synonyms:
                _add_token(table_by_token, synonym, table_name)

        for dimension in table.dimensions or []:
            dimension_tokens = [dimension.name, dimension.alias, *(dimension.synonyms or [])]
            for token in _explode_synonyms(dimension_tokens):
                _add_token_pair(column_by_token, token, table_name, dimension.name)

        for measure in table.measures or []:
            _add_token_pair(column_by_token, measure.name, table_name, measure.name)

        for filter_key, table_filter in (table.filters or {}).items():
            _add_token(filter_by_token, filter_key, (table_name, filter_key))  # type: ignore[arg-type]
            if table_filter.synonyms:
                for synonym in table_filter.synonyms:
                    _add_token(filter_by_token, synonym, (table_name, filter_key))  # type: ignore[arg-type]

    for metric_key in (model.metrics or {}):
        _add_token(metric_by_token, metric_key, metric_key)

    for table_name, table in model.tables.items():
        for dimension in table.dimensions or []:
            _add_token_pair(column_by_token, f"{table_name}.{dimension.name}", table_name, dimension.name)
        for measure in table.measures or []:
            _add_token_pair(column_by_token, f"{table_name}.{measure.name}", table_name, measure.name)

    return ResolvedModel(
        model=model,
        table_by_token=table_by_token,
        column_by_token=column_by_token,
        filter_by_token=filter_by_token,
        metric_by_token=metric_by_token,
    )


__all__ = ["ResolvedModel", "build_resolved_model"]
