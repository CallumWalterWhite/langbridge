

from typing import Any, Dict, List, Optional
from uuid import UUID

from models.base import _Base

class SemanticQueryMetaResponse(_Base):
    id: UUID

class SemanticQueryRequest(_Base):
    organization_id: UUID
    project_id: Optional[UUID] = None
    semantic_model_id: UUID
    query: Dict[str, Any]

class SemanticQueryResponse(_Base):
    id: UUID
    organization_id: UUID
    project_id: Optional[UUID] = None
    semantic_model_id: UUID
    data: List[Dict[str, Any]]
    annotations: List[Dict[str, Any]]