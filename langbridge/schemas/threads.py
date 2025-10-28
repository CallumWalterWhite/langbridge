from typing import Any, Dict, Optional
from uuid import UUID

from .base import _Base


class ThreadResponse(_Base):
    id: Optional[UUID] = None
    project_id: Optional[UUID] = None
    title: Optional[str] = None
    status: str = "active"
    metadata_json: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class ThreadListResponse(_Base):
    threads: list[ThreadResponse] = []

class ThreadCreateRequest(_Base):
    project_id: Optional[UUID] = None
    title: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None

class ThreadUpdateRequest(_Base):
    title: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None

#Test
class ThreadChatRequest(_Base):
    message: str