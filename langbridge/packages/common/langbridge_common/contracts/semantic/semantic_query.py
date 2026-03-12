from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import Field, model_validator

from langbridge.packages.common.langbridge_common.contracts.base import _Base


class SemanticQueryMetaResponse(_Base):
    id: UUID
    name: str
    description: str | None = None
    connector_id: UUID | None = None
    organization_id: UUID
    project_id: UUID | None = None
    semantic_model: dict[str, Any]


class SemanticQueryRequest(_Base):
    organization_id: UUID
    project_id: UUID | None = None
    semantic_model_id: UUID
    query: dict[str, Any]


class SemanticQueryResponse(_Base):
    id: UUID
    organization_id: UUID
    project_id: UUID | None = None
    semantic_model_id: UUID
    data: list[dict[str, Any]]
    annotations: list[dict[str, Any]]
    metadata: list[dict[str, Any]] | None = None


class UnifiedSemanticJoinRequest(_Base):
    name: str | None = None
    source_dataset: str
    source_field: str
    target_dataset: str
    target_field: str
    operator: str = "="
    type: str = "inner"

    @model_validator(mode="before")
    @classmethod
    def _normalize_legacy_join_shape(cls, payload: Any) -> Any:
        if not isinstance(payload, dict):
            return payload
        if payload.get("source_dataset") and payload.get("target_dataset"):
            return payload
        source_dataset = payload.get("from_") or payload.get("from") or payload.get("left_table") or payload.get("leftTable")
        target_dataset = payload.get("to") or payload.get("target") or payload.get("right_table") or payload.get("rightTable")
        join_condition = payload.get("on") or payload.get("join_on") or payload.get("condition")
        if not source_dataset or not target_dataset or not isinstance(join_condition, str):
            return payload
        normalized = join_condition.replace("==", "=").strip()
        if "=" not in normalized:
            return payload
        left_raw, right_raw = [part.strip() for part in normalized.split("=", 1)]
        left_dataset, left_field = cls._split_member(left_raw)
        right_dataset, right_field = cls._split_member(right_raw)
        if not left_dataset or not left_field or not right_dataset or not right_field:
            return payload
        return {
            "name": payload.get("name"),
            "source_dataset": source_dataset,
            "source_field": left_field if left_dataset == source_dataset else right_field,
            "target_dataset": target_dataset,
            "target_field": right_field if right_dataset == target_dataset else left_field,
            "operator": payload.get("operator") or "=",
            "type": payload.get("type") or payload.get("join_type") or "inner",
        }

    @staticmethod
    def _split_member(member: str) -> tuple[str | None, str | None]:
        value = str(member or "").strip()
        if "." not in value:
            return None, None
        dataset_name, field_name = value.split(".", 1)
        return dataset_name.strip(), field_name.strip()


class UnifiedSemanticMetricRequest(_Base):
    expression: str
    description: str | None = None


class UnifiedSemanticQueryRequest(_Base):
    organization_id: UUID
    project_id: UUID | None = None
    connector_id: UUID | None = None
    semantic_model_ids: list[UUID]
    joins: list[UnifiedSemanticJoinRequest] = Field(default_factory=list)
    metrics: dict[str, UnifiedSemanticMetricRequest] | None = None
    query: dict[str, Any]

    @model_validator(mode="after")
    def _validate_semantic_model_ids(self) -> "UnifiedSemanticQueryRequest":
        if not self.semantic_model_ids:
            raise ValueError("semantic_model_ids must include at least one model id.")
        return self


class UnifiedSemanticQueryMetaRequest(_Base):
    organization_id: UUID
    project_id: UUID | None = None
    connector_id: UUID | None = None
    semantic_model_ids: list[UUID]
    joins: list[UnifiedSemanticJoinRequest] = Field(default_factory=list)
    metrics: dict[str, UnifiedSemanticMetricRequest] | None = None

    @model_validator(mode="after")
    def _validate_semantic_model_ids(self) -> "UnifiedSemanticQueryMetaRequest":
        if not self.semantic_model_ids:
            raise ValueError("semantic_model_ids must include at least one model id.")
        return self


class UnifiedSemanticQueryMetaResponse(_Base):
    connector_id: UUID
    organization_id: UUID
    project_id: UUID | None = None
    semantic_model_ids: list[UUID]
    semantic_model: dict[str, Any]


class UnifiedSemanticQueryResponse(_Base):
    id: UUID
    organization_id: UUID
    project_id: UUID | None = None
    connector_id: UUID
    semantic_model_ids: list[UUID]
    data: list[dict[str, Any]]
    annotations: list[dict[str, Any]]
    metadata: list[dict[str, Any]] | None = None


class SemanticQueryJobResponse(_Base):
    job_id: UUID
    job_status: str
