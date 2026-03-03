from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import Field, model_validator

from langbridge.packages.common.langbridge_common.contracts.base import _Base

from .type import JobType


class CreateDatasetPreviewJobRequest(_Base):
    job_type: JobType = JobType.DATASET_PREVIEW
    dataset_id: uuid.UUID
    workspace_id: uuid.UUID
    project_id: uuid.UUID | None = None
    user_id: uuid.UUID
    requested_limit: int | None = Field(default=None, ge=1)
    enforced_limit: int = Field(..., ge=1)
    filters: dict[str, Any] = Field(default_factory=dict)
    sort: list[dict[str, Any]] = Field(default_factory=list)
    user_context: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str | None = None
    operation: Literal["preview"] = "preview"

    @model_validator(mode="after")
    def _validate_request(self) -> "CreateDatasetPreviewJobRequest":
        if self.requested_limit is not None and self.requested_limit < 1:
            raise ValueError("requested_limit must be greater than zero when supplied.")
        return self


class CreateDatasetProfileJobRequest(_Base):
    job_type: JobType = JobType.DATASET_PROFILE
    dataset_id: uuid.UUID
    workspace_id: uuid.UUID
    project_id: uuid.UUID | None = None
    user_id: uuid.UUID
    user_context: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str | None = None
    operation: Literal["profile"] = "profile"
