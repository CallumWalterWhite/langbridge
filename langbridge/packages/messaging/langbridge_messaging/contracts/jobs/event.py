import uuid
from typing import Any

from ..base import BaseMessagePayload, register_payload

@register_payload("job_event")
class JobEventMessage(BaseMessagePayload):
    """Payload for emitting a job event."""
    job_id: uuid.UUID
    event_type: str
    message: str
    visibility: str
    source: str | None = None
    details: dict[str, Any] | None = None
