from __future__ import annotations

import uuid
from typing import Any

from langbridge.contracts.jobs.type import JobType

from ..base import BaseMessagePayload, MessageType, register_payload


@register_payload(MessageType.SQL_JOB_REQUEST.value)
class SqlJobRequestMessage(BaseMessagePayload):
    message_type: MessageType = MessageType.SQL_JOB_REQUEST
    sql_job_id: uuid.UUID | None = None
    job_id: uuid.UUID | None = None
    job_type: JobType = JobType.SQL
    job_request: dict[str, Any]


__all__ = ["SqlJobRequestMessage"]
