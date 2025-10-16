"""
Utility functions for loading semantic models from YAML definitions.
"""
import yaml
from yaml.parser import ParserError
from yaml.scanner import ScannerError

from semantic import SemanticModel


class SemanticModelLoadError(RuntimeError):
    """Raised when a semantic model cannot be parsed from YAML."""


def load_semantic_model_yaml(yaml_text: str) -> SemanticModel:
    """
    Parse a semantic model definition from YAML text.
    """

    try:
        data = yaml.safe_load(yaml_text)
    except (ScannerError, ParserError) as exc:
        raise SemanticModelLoadError("Failed to parse semantic model YAML.") from exc

    if not isinstance(data, dict):
        raise SemanticModelLoadError("Semantic model YAML must parse to a mapping.")

    try:
        return SemanticModel.model_validate(data)
    except ValueError as exc:
        raise SemanticModelLoadError("Semantic model YAML failed validation.") from exc


__all__ = ["load_semantic_model_yaml", "SemanticModelLoadError"]
