import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, ForeignKey, JSON, String, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class BIDashboard(Base):
    __tablename__ = "bi_dashboards"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("projects.id"),
        nullable=True,
        index=True,
    )
    semantic_model_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("semantic_models.id"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    refresh_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    data_snapshot_format: Mapped[str] = mapped_column(String(32), nullable=False, default="json")
    data_snapshot_reference: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    last_refreshed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    global_filters: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    widgets: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
