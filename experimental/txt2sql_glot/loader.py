from typing import Any
import yaml
from model import SemanticModel

def load_semantic_model_yaml(yaml_text: str) -> SemanticModel:
    data = yaml.safe_load(yaml_text)
    return SemanticModel.model_validate(data)