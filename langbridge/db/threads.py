from sqlalchemy import (
    String, Enum, ForeignKey, DateTime, Integer, UUID, func
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
import enum, uuid
from .base import Base

class ThreadStatus(enum.Enum):
    active="active"; archived="archived"; error="error"; completed="completed"

class Role(enum.Enum):
    system="system"; user="user"; assistant="assistant"; tool="tool"

class Thread(Base):
    __tablename__ = "threads"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[ThreadStatus] = mapped_column(Enum(ThreadStatus), default=ThreadStatus.active)
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="cascade"))

class Message(Base):
    __tablename__ = "messages"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    thread_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("threads.id", ondelete="cascade"), index=True)
    parent_message_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    role: Mapped[Role] = mapped_column(Enum(Role))
    content: Mapped[dict] = mapped_column(JSONB)  # array-of-parts schema
    model_snapshot: Mapped[dict | None] = mapped_column(JSONB)
    token_usage: Mapped[dict | None] = mapped_column(JSONB)  # {prompt, completion, total, costs...}
    error: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped = mapped_column(DateTime(timezone=True), server_default=func.now())

class RunStatus(enum.Enum):
    running="running"; succeeded="succeeded"; failed="failed"; cancelled="cancelled"

class Run(Base):
    __tablename__ = "runs"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    thread_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("threads.id", ondelete="cascade"), index=True)
    root_message_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("messages.id", ondelete="cascade"))
    graph: Mapped[dict | None] = mapped_column(JSONB)
    state_before: Mapped[dict | None] = mapped_column(JSONB)
    state_after: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[RunStatus] = mapped_column(Enum(RunStatus), default=RunStatus.running)
    started_at: Mapped = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[DateTime | None]
    latency_ms: Mapped[int | None] = mapped_column(Integer)

class ToolCall(Base):
    __tablename__ = "tool_calls"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    message_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("messages.id", ondelete="cascade"), index=True)
    tool_name: Mapped[str] = mapped_column(String)
    arguments: Mapped[dict] = mapped_column(JSONB)
    result: Mapped[dict | None] = mapped_column(JSONB)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped = mapped_column(DateTime(timezone=True), server_default=func.now())
