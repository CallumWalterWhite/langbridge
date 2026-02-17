
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import Field, model_validator

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


class UnifiedSemanticJoinRequest(_Base):
    name: Optional[str] = None
    from_: str
    to: str
    type: str = "inner"
    on: str


class UnifiedSemanticMetricRequest(_Base):
    expression: str
    description: Optional[str] = None


class UnifiedSemanticQueryRequest(_Base):
    organization_id: UUID
    project_id: Optional[UUID] = None
    connector_id: UUID
    semantic_model_ids: List[UUID]
    joins: List[UnifiedSemanticJoinRequest] = Field(default_factory=list)
    metrics: Optional[Dict[str, UnifiedSemanticMetricRequest]] = None
    query: Dict[str, Any]

    @model_validator(mode="after")
    def _validate_semantic_model_ids(self) -> "UnifiedSemanticQueryRequest":
        if not self.semantic_model_ids:
            raise ValueError("semantic_model_ids must include at least one model id.")
        return self


class UnifiedSemanticQueryMetaRequest(_Base):
    organization_id: UUID
    project_id: Optional[UUID] = None
    connector_id: UUID
    semantic_model_ids: List[UUID]
    joins: List[UnifiedSemanticJoinRequest] = Field(default_factory=list)
    metrics: Optional[Dict[str, UnifiedSemanticMetricRequest]] = None

    @model_validator(mode="after")
    def _validate_semantic_model_ids(self) -> "UnifiedSemanticQueryMetaRequest":
        if not self.semantic_model_ids:
            raise ValueError("semantic_model_ids must include at least one model id.")
        return self


class UnifiedSemanticQueryMetaResponse(_Base):
    connector_id: UUID
    organization_id: UUID
    project_id: Optional[UUID] = None
    semantic_model_ids: List[UUID]
    semantic_model: Dict[str, Any]


class UnifiedSemanticQueryResponse(_Base):
    id: UUID
    organization_id: UUID
    project_id: Optional[UUID] = None
    connector_id: UUID
    semantic_model_ids: List[UUID]
    data: List[Dict[str, Any]]
    annotations: List[Dict[str, Any]]
    metadata: Optional[List[Dict[str, Any]]] = None


class SemanticQueryJobResponse(_Base):
    job_id: UUID
    job_status: str
