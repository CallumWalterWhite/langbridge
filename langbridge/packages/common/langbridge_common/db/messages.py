import enum
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import DateTime, Enum as SAEnum, JSON, String, UUID, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class MessageStatus(enum.Enum):
    received = "received"
    processing = "processing"
    completed = "completed"
    failed = "failed"
    dead_letter = "dead_letter"


class MessageRecord(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_type: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    payload: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    headers: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[MessageStatus] = mapped_column(
        SAEnum(MessageStatus, name="message_status"),
        nullable=False,
        default=MessageStatus.received,
        index=True,
    )

    stream: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    consumer_group: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    consumer_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    entry_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    error: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    received_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
