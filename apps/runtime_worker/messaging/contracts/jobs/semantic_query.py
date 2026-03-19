from __future__ import annotations

import uuid
from typing import Any

from langbridge.contracts.jobs.type import JobType

from ..base import BaseMessagePayload, MessageType, register_payload


@register_payload(MessageType.SEMANTIC_QUERY_REQUEST.value)
class SemanticQueryRequestMessage(BaseMessagePayload):
    message_type: MessageType = MessageType.SEMANTIC_QUERY_REQUEST
    job_id: uuid.UUID | None = None
    job_type: JobType = JobType.SEMANTIC_QUERY
    job_request: dict[str, Any] | None = None


__all__ = ["SemanticQueryRequestMessage"]
