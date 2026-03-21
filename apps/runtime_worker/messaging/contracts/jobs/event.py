from __future__ import annotations

import uuid
from typing import Any

from ..base import BaseMessagePayload, MessageType, register_payload


@register_payload(MessageType.JOB_EVENT.value)
class JobEventMessage(BaseMessagePayload):
    message_type: MessageType = MessageType.JOB_EVENT
    job_id: uuid.UUID
    event_type: str
    message: str
    visibility: str = "internal"
    source: str | None = None
    details: dict[str, Any] = {}


__all__ = ["JobEventMessage"]
