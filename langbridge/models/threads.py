from typing import Any, Dict, Optional, Union
from uuid import UUID
from datetime import datetime

from pydantic import Field

from .base import _Base


class ThreadResponse(_Base):
    id: Optional[UUID] = None
    project_id: Optional[UUID] = None
    title: Optional[str] = None
    status: str = "active"
    metadata_json: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ThreadListResponse(_Base):
    threads: list[ThreadResponse] = Field(default_factory=list)


class ThreadCreateRequest(_Base):
    project_id: Optional[UUID] = None
    title: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None


class ThreadUpdateRequest(_Base):
    title: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None


class ThreadChatRequest(_Base):
    message: str


class ThreadTabularResult(_Base):
    columns: list[str] = Field(default_factory=list)
    rows: list[Any] = Field(default_factory=list)
    row_count: Optional[int] = None
    elapsed_ms: Optional[int] = None


class ThreadVisualizationSpec(_Base):
    chart_type: Optional[str] = None
    x: Optional[str] = None
    y: Optional[Union[list[str], str]] = None
    group_by: Optional[str] = None
    title: Optional[str] = None
    options: Optional[Dict[str, Any]] = None


class ThreadChatResponse(_Base):
    result: Optional[ThreadTabularResult] = None
    visualization: Optional[ThreadVisualizationSpec] = None
    summary: Optional[str] = None
