from __future__ import annotations

import uuid
from typing import Any

from langbridge.contracts.jobs.type import JobType

from ..base import BaseMessagePayload, MessageType, register_payload


@register_payload(MessageType.CONNECTOR_SYNC_JOB_REQUEST.value)
class ConnectorSyncJobRequestMessage(BaseMessagePayload):
    message_type: MessageType = MessageType.CONNECTOR_SYNC_JOB_REQUEST
    job_id: uuid.UUID
    job_type: JobType = JobType.CONNECTOR_SYNC
    job_request: dict[str, Any]


__all__ = ["ConnectorSyncJobRequestMessage"]
