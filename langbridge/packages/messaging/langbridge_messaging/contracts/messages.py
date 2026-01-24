from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


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
    message_type: str
    payload: dict[str, Any]
    headers: MessageHeaders = Field(default_factory=MessageHeaders)
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))

    def increment_attempt(self) -> None:
        self.headers.attempt += 1

    def to_json(self) -> str:
        return self.model_dump_json()

    @classmethod
    def from_json(cls, raw: str) -> "MessageEnvelope":
        return cls.model_validate_json(raw)
