from typing import Any
import uuid

from langbridge.packages.common.langbridge_common.contracts.base import _Base

from .type import JobType


class CreateSemanticQueryJobRequest(_Base):
    job_type: JobType = JobType.SEMANTIC_QUERY
    organisation_id: uuid.UUID
    project_id: uuid.UUID | None = None
    user_id: uuid.UUID
    semantic_model_id: uuid.UUID
    query: dict[str, Any]
