

from typing import Any, Dict, List, Optional
from uuid import UUID

from langbridge.packages.common.langbridge_common.contracts.base import _Base

class SemanticQueryMetaResponse(_Base):
    id: UUID
    name: str
    description: Optional[str] = None
    connector_id: UUID
    organization_id: UUID
    project_id: Optional[UUID] = None
    semantic_model: Dict[str, Any]

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
    metadata: Optional[List[Dict[str, Any]]] = None


class SemanticQueryJobResponse(_Base):
    job_id: UUID
    job_status: str
