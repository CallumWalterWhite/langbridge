import yaml
from typing import Dict, List, Optional
from pydantic import BaseModel
from langbridge.packages.semantic.langbridge_semantic.model import Metric, SemanticModel, Relationship

class UnifiedSemanticModel(BaseModel):
    semantic_models: List[SemanticModel]
    version: str
    description: Optional[str] = None
    relationships: Optional[List[Relationship]] = None
    metrics: Optional[Dict[str, Metric]] = None

    def yml_dump(self) -> str:
        """Dump the unified semantic model to a YAML string."""
        return yaml.dump(self.model_dump(by_alias=True), sort_keys=False)