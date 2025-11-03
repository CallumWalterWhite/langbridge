from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import String, Enum as SAEnum, ForeignKey, DateTime, Integer, UUID, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class ThreadStatus(enum.Enum):
    active = "active"
    archived = "archived"
    error = "error"
    completed = "completed"


class Role(enum.Enum):
    system = "system"
    user = "user"
    assistant = "assistant"
    tool = "tool"


class Thread(Base):
    __tablename__ = "threads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    title: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Name enums in DB to avoid anonymous enum issues
    status: Mapped[ThreadStatus] = mapped_column(SAEnum(ThreadStatus, name="thread_status"),
                                                 default=ThreadStatus.active)

    # Column name is "metadata" in DB, Python attr is metadata_json (avoids Base.metadata clash)
    # metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column("metadata", JSONB, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="cascade"), nullable=False)


# class Message(Base):
#     __tablename__ = "messages"

#     id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
#     thread_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("threads.id", ondelete="cascade"), index=True)
#     parent_message_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)

#     role: Mapped[Role] = mapped_column(SAEnum(Role, name="message_role"), nullable=False)

#     content: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)  # array-of-parts schema
#     model_snapshot: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)
#     token_usage: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)  # {prompt, completion, total, costs...}
#     error: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)

#     created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# class RunStatus(enum.Enum):
#     running = "running"
#     succeeded = "succeeded"
#     failed = "failed"
#     cancelled = "cancelled"


# class Run(Base):
#     __tablename__ = "runs"

#     id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
#     thread_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("threads.id", ondelete="cascade"), index=True)
#     root_message_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("messages.id", ondelete="cascade"))

#     graph: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)
#     state_before: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)
#     state_after: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)

#     status: Mapped[RunStatus] = mapped_column(SAEnum(RunStatus, name="run_status"), default=RunStatus.running)

#     started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
#     finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

#     latency_ms: Mapped[Optional[int]] = mapped_column(Integer)


# class ToolCall(Base):
#     __tablename__ = "tool_calls"

#     id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
#     message_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("messages.id", ondelete="cascade"), index=True)

#     tool_name: Mapped[str] = mapped_column(String)
#     arguments: Mapped[Dict[str, Any]] = mapped_column(JSONB)
#     result: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)
#     duration_ms: Mapped[Optional[int]] = mapped_column(Integer)
#     error: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)

#     created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
