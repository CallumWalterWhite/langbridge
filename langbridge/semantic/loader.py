from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Iterable, Optional

import yaml

from semantic.model import Dimension, Measure, Metric, Relationship, SemanticModel, Table, TableFilter


class SemanticModelError(ValueError):
    """Raised when a semantic model definition cannot be parsed or validated."""


def load_semantic_model(source: str | Mapping[str, Any] | Path) -> SemanticModel:
    if isinstance(source, Path):
        return load_semantic_model(source.read_text(encoding="utf-8"))
    if isinstance(source, Mapping):
        payload = dict(source)
    else:
        try:
            payload = yaml.safe_load(source)
        except yaml.YAMLError as exc:
            raise SemanticModelError(f"Unable to parse semantic model payload: {exc}") from exc

    if not isinstance(payload, Mapping):
        raise SemanticModelError("Semantic model payload must be a mapping.")

    return parse_semantic_model_payload(payload)


def parse_semantic_model_payload(payload: Mapping[str, Any]) -> SemanticModel:
    if "semantic_models" in payload:
        return _parse_unified_payload(payload)
    if "tables" in payload:
        return _parse_tables_payload(payload)
    if "entities" in payload:
        return _parse_entities_payload(payload)
    raise SemanticModelError("Semantic model payload must define tables, entities, or semantic_models.")


def _parse_tables_payload(payload: Mapping[str, Any]) -> SemanticModel:
    normalized = dict(payload)
    if "version" not in normalized:
        normalized["version"] = "1.0"
    return SemanticModel.model_validate(normalized)


def _parse_unified_payload(payload: Mapping[str, Any]) -> SemanticModel:
    raw_models = payload.get("semantic_models") or []
    if not isinstance(raw_models, list) or not raw_models:
        raise SemanticModelError("Unified semantic model must define at least one semantic model.")

    merged_tables: dict[str, Table] = {}
    merged_relationships: list[Relationship] = []
    merged_metrics: dict[str, Metric] = {}
    merged_tags: list[str] = []

    for entry in raw_models:
        if not isinstance(entry, Mapping):
            raise SemanticModelError("Unified semantic model entries must be mappings.")
        model = parse_semantic_model_payload(entry)
        for table_key, table in model.tables.items():
            if table_key in merged_tables:
                raise SemanticModelError(f"Duplicate table key '{table_key}' in unified semantic model.")
            merged_tables[table_key] = table
        if model.relationships:
            merged_relationships.extend(model.relationships)
        if model.metrics:
            for metric_key, metric in model.metrics.items():
                if metric_key not in merged_metrics:
                    merged_metrics[metric_key] = metric
        if model.tags:
            merged_tags.extend([tag for tag in model.tags if tag not in merged_tags])

    relationship_source = payload.get("relationships") or payload.get("joins") or []
    merged_relationships.extend(_parse_relationships(relationship_source))

    metric_source = payload.get("metrics") or {}
    merged_metrics.update(_parse_metrics(metric_source))

    name = payload.get("name")
    description = payload.get("description")
    connector = payload.get("connector")
    dialect = payload.get("dialect")
    tags = payload.get("tags") or merged_tags
    version = payload.get("version") or "1.0"

    return SemanticModel(
        version=version,
        name=name,
        description=description,
        connector=connector,
        dialect=dialect,
        tags=list(tags) if isinstance(tags, Iterable) and not isinstance(tags, str) else None,
        tables=merged_tables,
        relationships=merged_relationships or None,
        metrics=merged_metrics or None,
    )


def _parse_entities_payload(payload: Mapping[str, Any]) -> SemanticModel:
    entities = payload.get("entities") or {}
    if not isinstance(entities, Mapping) or not entities:
        raise SemanticModelError("Entities payload must define at least one entity.")

    dimension_map = payload.get("dimensions") or {}
    metrics_map = payload.get("metrics") or {}
    joins_source = payload.get("joins") or payload.get("relationships") or []

    tables: dict[str, Table] = {}
    for entity_name, entity_meta in entities.items():
        if not isinstance(entity_meta, Mapping):
            continue
        table = _parse_entity_table(entity_name, entity_meta, dimension_map)
        tables[entity_name] = table

    metrics = _parse_metrics(metrics_map)
    relationships = _parse_relationships(joins_source)

    normalized = {
        "version": payload.get("version") or "1.0",
        "name": payload.get("name"),
        "description": payload.get("description"),
        "connector": payload.get("connector"),
        "dialect": payload.get("dialect"),
        "tags": payload.get("tags"),
        "tables": tables,
        "relationships": relationships or None,
        "metrics": metrics or None,
    }
    return SemanticModel.model_validate(normalized)


def _parse_entity_table(
    entity_name: str,
    entity_meta: Mapping[str, Any],
    dimension_map: Mapping[str, Any],
) -> Table:
    schema = entity_meta.get("schema")
    table_name = entity_meta.get("name") or entity_meta.get("table")
    if isinstance(table_name, str) and "." in table_name and not schema:
        schema, table_name = table_name.split(".", 1)

    columns = entity_meta.get("columns") or {}
    raw_primary_keys = entity_meta.get("primary_key") or []
    if isinstance(raw_primary_keys, str):
        primary_keys = {raw_primary_keys}
    elif isinstance(raw_primary_keys, list):
        primary_keys = {str(item) for item in raw_primary_keys if item}
    else:
        primary_keys = set()

    dimensions: list[Dimension] = []
    measures: list[Measure] = []

    for column_name, raw_meta in columns.items():
        column_meta = raw_meta if isinstance(raw_meta, Mapping) else {}
        role = str(column_meta.get("role") or "").strip().lower()
        data_type = column_meta.get("type") or column_meta.get("dtype") or "string"

        if role == "measure":
            measures.append(
                Measure(
                    name=column_name,
                    type=str(data_type),
                    description=_string_or_none(column_meta.get("description")),
                    aggregation=_string_or_none(column_meta.get("aggregation") or column_meta.get("agg")),
                    synonyms=_list_or_none(column_meta.get("synonyms")),
                )
            )
            continue

        dimension_meta = _resolve_dimension_meta(entity_name, column_name, dimension_map)
        dimension = _build_dimension(
            column_name=column_name,
            data_type=str(data_type),
            column_meta=column_meta,
            dimension_meta=dimension_meta,
            primary_keys=primary_keys,
        )
        dimensions.append(dimension)

    for dimension_key, raw_meta in dimension_map.items():
        meta = raw_meta if isinstance(raw_meta, Mapping) else {}
        target_entity = meta.get("entity")
        column = meta.get("column")
        if not target_entity or not column:
            if isinstance(dimension_key, str) and "." in dimension_key:
                target_entity, column = dimension_key.split(".", 1)
        if target_entity != entity_name or not column:
            continue
        if any(dimension.name == column for dimension in dimensions):
            continue
        data_type = meta.get("type") or "string"
        dimension = _build_dimension(
            column_name=str(column),
            data_type=str(data_type),
            column_meta={},
            dimension_meta=meta,
            primary_keys=primary_keys,
        )
        dimensions.append(dimension)

    filters_raw = entity_meta.get("filters") or {}
    filters: dict[str, TableFilter] | None = None
    if isinstance(filters_raw, Mapping) and filters_raw:
        filters = {
            str(filter_key): TableFilter(
                condition=str(filter_meta.get("condition", "")),
                description=_string_or_none(filter_meta.get("description")),
                synonyms=_list_or_none(filter_meta.get("synonyms")),
            )
            for filter_key, filter_meta in filters_raw.items()
            if isinstance(filter_meta, Mapping) and filter_meta.get("condition")
        }

    return Table(
        schema=str(schema or ""),
        name=str(table_name or ""),
        description=_string_or_none(entity_meta.get("description")),
        synonyms=_list_or_none(entity_meta.get("synonyms")),
        dimensions=dimensions or None,
        measures=measures or None,
        filters=filters or None,
    )


def _resolve_dimension_meta(
    entity_name: str, column_name: str, dimension_map: Mapping[str, Any]
) -> Mapping[str, Any]:
    dimension_key = f"{entity_name}.{column_name}"
    raw = dimension_map.get(dimension_key)
    if isinstance(raw, Mapping):
        return raw
    return {}


def _build_dimension(
    *,
    column_name: str,
    data_type: str,
    column_meta: Mapping[str, Any],
    dimension_meta: Mapping[str, Any],
    primary_keys: set[str],
) -> Dimension:
    description = _string_or_none(dimension_meta.get("description") or column_meta.get("description"))
    alias = _string_or_none(dimension_meta.get("alias") or column_meta.get("alias"))
    synonyms = _list_or_none(dimension_meta.get("synonyms") or column_meta.get("synonyms"))
    vectorized = bool(dimension_meta.get("vectorized") or column_meta.get("vectorized"))
    vector_reference = dimension_meta.get("vector_reference") or column_meta.get("vector_reference")
    vector_index = dimension_meta.get("vector_index") or column_meta.get("vector_index")
    primary_key = bool(
        column_meta.get("primary_key")
        or column_name in primary_keys
        or str(column_meta.get("role") or "").strip().lower() == "primary_key"
    )

    return Dimension(
        name=str(column_name),
        type=str(data_type),
        primary_key=primary_key,
        alias=alias,
        description=description,
        synonyms=synonyms,
        vectorized=vectorized,
        vector_reference=_string_or_none(vector_reference),
        vector_index=vector_index if isinstance(vector_index, Mapping) else None,
    )


def _parse_relationships(source: Any) -> list[Relationship]:
    relationships: list[Relationship] = []
    if not isinstance(source, list):
        return relationships

    for item in source:
        if not isinstance(item, Mapping):
            continue
        left = item.get("left") or item.get("from") or item.get("from_")
        right = item.get("right") or item.get("to")
        condition = item.get("on") or item.get("join_on") or item.get("condition")
        if not left or not right or not condition:
            continue

        rel_type = (
            item.get("cardinality")
            or item.get("relationship")
            or item.get("type")
            or "many_to_one"
        )
        rel_type = str(rel_type).strip().lower()

        relationships.append(
            Relationship(
                name=str(item.get("name") or f"{left}_to_{right}"),
                from_=str(left),
                to=str(right),
                type=rel_type,
                join_on=str(condition),
            )
        )
    return relationships


def _parse_metrics(source: Any) -> dict[str, Metric]:
    metrics: dict[str, Metric] = {}
    if not isinstance(source, Mapping):
        return metrics

    for key, value in source.items():
        if isinstance(value, Mapping):
            expression = value.get("expression") or value.get("sql") or value.get("expr")
            if not expression:
                continue
            metrics[str(key)] = Metric(
                expression=str(expression),
                description=_string_or_none(value.get("description")),
            )
        elif isinstance(value, str):
            metrics[str(key)] = Metric(expression=value)
    return metrics


def _list_or_none(value: Any) -> Optional[list[str]]:
    if not value:
        return None
    if isinstance(value, list):
        items = [str(item) for item in value if item is not None and str(item).strip()]
        return items or None
    if isinstance(value, str):
        cleaned = value.strip()
        return [cleaned] if cleaned else None
    return None


def _string_or_none(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


__all__ = ["SemanticModelError", "load_semantic_model", "parse_semantic_model_payload"]
