"""
Utility functions for loading semantic models from YAML definitions.
"""
from langbridge.packages.semantic.langbridge_semantic import SemanticModel
from langbridge.packages.semantic.langbridge_semantic.loader import SemanticModelError, load_semantic_model


class SemanticModelLoadError(RuntimeError):
    """Raised when a semantic model cannot be parsed from YAML."""


def load_semantic_model_yaml(yaml_text: str) -> SemanticModel:
    """
    Parse a semantic model definition from YAML text.
    """
    try:
        return load_semantic_model(yaml_text)
    except SemanticModelError as exc:
        raise SemanticModelLoadError(str(exc)) from exc


__all__ = ["load_semantic_model_yaml", "SemanticModelLoadError"]
