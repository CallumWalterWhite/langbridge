

from typing import Optional
from uuid import UUID

from models.base import _Base

class SemanticQueryRequest(_Base):
    organization_id: UUID
    project_id: Optional[UUID] = None
    semantic_model_id: UUID
    query: str

class SemanticQueryResponse(_Base):
    id: UUID
    organization_id: UUID
    project_id: Optional[UUID] = None
    semantic_model_id: UUID
    response: str