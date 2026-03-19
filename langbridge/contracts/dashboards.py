from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import Field, field_validator

from .base import _Base


class DashboardRefreshMode(str, Enum):
    manual = "manual"
    live = "live"


class DashboardDataFormat(str, Enum):
    json = "json"


class DashboardCreateRequest(_Base):
    project_id: Optional[UUID] = None
    semantic_model_id: UUID
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=1024)
    refresh_mode: DashboardRefreshMode = DashboardRefreshMode.manual
    global_filters: list[dict[str, Any]] = Field(default_factory=list)
    widgets: list[dict[str, Any]] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Dashboard name is required.")
        return normalized


class DashboardUpdateRequest(_Base):
    project_id: Optional[UUID] = None
    semantic_model_id: Optional[UUID] = None
    name: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = Field(default=None, max_length=1024)
    refresh_mode: Optional[DashboardRefreshMode] = None
    global_filters: Optional[list[dict[str, Any]]] = None
    widgets: Optional[list[dict[str, Any]]] = None

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip()
        if not normalized:
            raise ValueError("Dashboard name is required.")
        return normalized


class DashboardResponse(_Base):
    id: UUID
    organization_id: UUID
    project_id: Optional[UUID] = None
    semantic_model_id: UUID
    name: str
    description: Optional[str] = None
    refresh_mode: DashboardRefreshMode
    data_snapshot_format: DashboardDataFormat
    last_refreshed_at: Optional[datetime] = None
    global_filters: list[dict[str, Any]]
    widgets: list[dict[str, Any]]
    created_by: UUID
    created_at: datetime
    updated_at: datetime


class DashboardSnapshotUpsertRequest(_Base):
    data: dict[str, Any] = Field(default_factory=dict)
    captured_at: Optional[datetime] = None


class DashboardSnapshotResponse(_Base):
    dashboard_id: UUID
    snapshot_format: DashboardDataFormat
    captured_at: datetime
    data: dict[str, Any]
