import uuid
from typing import Any

from langbridge.packages.common.langbridge_common.contracts.jobs.type import JobType

from ..base import BaseMessagePayload, register_payload


@register_payload("dataset_job_request")
class DatasetJobRequestMessage(BaseMessagePayload):
    """Payload for requesting worker-based dataset preview/profile execution."""

    job_id: uuid.UUID
    job_type: JobType
    job_request: dict[str, Any]
