from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import yaml

from langbridge.packages.semantic.langbridge_semantic.errors import SemanticModelError
from langbridge.packages.semantic.langbridge_semantic.model import Metric, Relationship, SemanticModel


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
    if "datasets" in payload or "tables" in payload:
        return _parse_standard_payload(payload)
    raise SemanticModelError("Semantic model payload must define datasets or semantic_models.")


def _parse_standard_payload(payload: Mapping[str, Any]) -> SemanticModel:
    normalized = dict(payload)
    raw_datasets = payload.get("datasets") if isinstance(payload.get("datasets"), Mapping) else payload.get("tables")
    if not isinstance(raw_datasets, Mapping) or not raw_datasets:
        raise SemanticModelError("Semantic model payload must define at least one dataset.")

    normalized["version"] = str(payload.get("version") or "1.0")
    normalized["datasets"] = _normalize_datasets(raw_datasets)
    normalized.pop("tables", None)
    normalized["relationships"] = _parse_relationships(payload.get("relationships") or payload.get("joins")) or None
    normalized["metrics"] = _parse_metrics(payload.get("metrics")) or None
    return SemanticModel.model_validate(normalized)


def _parse_unified_payload(payload: Mapping[str, Any]) -> SemanticModel:
    raw_models = payload.get("semantic_models") or []
    if not isinstance(raw_models, list) or not raw_models:
        raise SemanticModelError("Unified semantic model must define at least one semantic model.")

    merged_datasets: dict[str, Any] = {}
    merged_relationships: list[Relationship] = []
    merged_metrics: dict[str, Metric] = {}
    merged_tags: list[str] = []

    for entry in raw_models:
        if not isinstance(entry, Mapping):
            raise SemanticModelError("Unified semantic model entries must be mappings.")
        model = parse_semantic_model_payload(entry)
        for dataset_key, dataset in model.datasets.items():
            if dataset_key in merged_datasets:
                raise SemanticModelError(f"Duplicate dataset key '{dataset_key}' in unified semantic model.")
            merged_datasets[dataset_key] = dataset
        if model.relationships:
            merged_relationships.extend(model.relationships)
        if model.metrics:
            for metric_key, metric in model.metrics.items():
                if metric_key not in merged_metrics:
                    merged_metrics[metric_key] = metric
        if model.tags:
            for tag in model.tags:
                if tag not in merged_tags:
                    merged_tags.append(tag)

    merged_relationships.extend(_parse_relationships(payload.get("relationships") or payload.get("joins")))
    merged_metrics.update(_parse_metrics(payload.get("metrics")))

    normalized = {
        "version": str(payload.get("version") or "1.0"),
        "name": payload.get("name"),
        "description": payload.get("description"),
        "connector": payload.get("connector"),
        "dialect": payload.get("dialect"),
        "tags": _list_or_none(payload.get("tags")) or merged_tags or None,
        "datasets": merged_datasets,
        "relationships": merged_relationships or None,
        "metrics": merged_metrics or None,
    }
    return SemanticModel.model_validate(normalized)


def _normalize_datasets(raw_datasets: Mapping[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for dataset_key, raw_value in raw_datasets.items():
        if not isinstance(raw_value, Mapping):
            continue
        value = dict(raw_value)
        value.setdefault("relation_name", str(dataset_key))
        normalized[str(dataset_key)] = value
    return normalized


def _parse_relationships(value: Any) -> list[Relationship]:
    if not isinstance(value, list):
        return []
    relationships: list[Relationship] = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        try:
            relationships.append(Relationship.model_validate(dict(item)))
        except Exception as exc:
            raise SemanticModelError(f"Invalid semantic relationship: {exc}") from exc
    return relationships


def _parse_metrics(value: Any) -> dict[str, Metric]:
    if not isinstance(value, Mapping):
        return {}
    metrics: dict[str, Metric] = {}
    for metric_key, raw_value in value.items():
        if not isinstance(raw_value, Mapping):
            continue
        try:
            metrics[str(metric_key)] = Metric.model_validate(dict(raw_value))
        except Exception as exc:
            raise SemanticModelError(f"Invalid semantic metric '{metric_key}': {exc}") from exc
    return metrics


def _list_or_none(value: Any) -> list[str] | None:
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes)):
        return None
    items = [str(item) for item in value if str(item).strip()]
    return items or None
