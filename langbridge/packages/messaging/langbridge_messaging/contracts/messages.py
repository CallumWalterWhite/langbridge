from enum import Enum
import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_validator

from .base import BaseMessagePayload, get_payload_model

class MessageType(str, Enum):
    """Message types."""
    TEST = "test"

    def __str__(self) -> str:
        return self.value

class MessageHeaders(BaseModel):
    """Standardized message headers for tracing and delivery metadata."""

    content_type: str = "application/json"
    schema_version: str | None = None
    correlation_id: str | None = None
    causation_id: str | None = None
    trace_id: str | None = None
    span_id: str | None = None
    reply_to: str | None = None
    attempt: int = 0
    max_attempts: int | None = None


class MessageEnvelope(BaseModel):
    """Envelope for queued messages."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    message_type: MessageType
    payload: BaseMessagePayload
    headers: MessageHeaders = Field(default_factory=MessageHeaders)
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))

    @field_validator("payload", mode="before")
    @classmethod
    def _parse_payload(cls, value, info):
        message_type = info.data.get("message_type")
        if not message_type:
            return value
        model = get_payload_model(str(message_type))
        if model is None:
            return value
        if isinstance(value, model):
            return value
        return model.model_validate(value)

    def increment_attempt(self) -> None:
        self.headers.attempt += 1

    def to_json(self) -> str:
        return self.model_dump_json()

    @classmethod
    def from_json(cls, raw: str) -> "MessageEnvelope":
        return cls.model_validate_json(raw)
