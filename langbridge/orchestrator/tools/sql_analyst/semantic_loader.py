"""
Utilities for loading semantic model definitions from YAML or JSON sources.
"""


import json
from pathlib import Path
from typing import Any, Mapping

import yaml

from .interfaces import SemanticModel, UnifiedSemanticModel


class SemanticModelError(ValueError):
    """Raised when the semantic model definition is invalid."""


def _parse_semantic_payload(payload: Mapping[str, Any]) -> SemanticModel | UnifiedSemanticModel:
    if "entities" not in payload or not payload["entities"]:
        return _parse_unified_semantic_payload(payload)
    # Metrics or dimensions provide analytical knobs; require one of them to avoid empty models.
    has_metrics = bool(payload.get("metrics"))
    has_dimensions = bool(payload.get("dimensions"))
    if not (has_metrics or has_dimensions):
        raise SemanticModelError("Semantic model must define at least one metric or dimension.")

    if "name" not in payload:
        payload = {**payload, "name": payload.get("id", "semantic_model")}

    return SemanticModel.model_validate(payload)

def _parse_unified_semantic_payload(payload: Mapping[str, Any]) -> UnifiedSemanticModel:
    if "semantic_models" not in payload or not payload["semantic_models"]:
        raise SemanticModelError("Unified semantic model must define at least one semantic model.")

    if "name" not in payload:
        payload = {**payload, "name": payload.get("id", "unified_model")}

    return UnifiedSemanticModel.model_validate(payload)


def load_semantic_model(source: str | Path | Mapping[str, Any]) -> SemanticModel | UnifiedSemanticModel:
    """
    Load a semantic model definition from a path, raw text, or mapping.
    """
    if isinstance(source, Mapping):
        return _parse_semantic_payload(source)

    text: str
    if isinstance(source, Path):
        text = source.read_text(encoding="utf-8")
    else:
        text = source

    try:
        if isinstance(source, Path):
            if source.suffix.lower() in {".json"}:
                payload = json.loads(text)
        else:
            payload = yaml.safe_load(text)
    except (json.JSONDecodeError, yaml.YAMLError) as exc:
        raise SemanticModelError(f"Unable to parse semantic model: {exc}") from exc

    if not isinstance(payload, Mapping):
        raise SemanticModelError("Semantic model payload must be a mapping/dictionary.")

    return _parse_semantic_payload(payload)


__all__ = ["SemanticModelError", "load_semantic_model"]

