

from datetime import datetime
from typing import Optional
from uuid import UUID

import yaml

from pydantic import ConfigDict

from models.base import _Base


class SemanticModelCreateRequest(_Base):
    connector_id: UUID
    organization_id: UUID
    project_id: Optional[UUID] = None
    name: str
    description: Optional[str] = None
    model_yaml: Optional[str] = None
    auto_generate: bool = False


class SemanticModelUpdateRequest(_Base):
    connector_id: Optional[UUID] = None
    project_id: Optional[UUID] = None
    name: Optional[str] = None
    description: Optional[str] = None
    model_yaml: Optional[str] = None
    auto_generate: bool = False


class SemanticModelRecordResponse(_Base):
    id: UUID
    organization_id: UUID
    project_id: Optional[UUID] = None
    name: str
    description: Optional[str] = None
    content_yaml: str
    created_at: datetime
    updated_at: datetime
    connector_id: UUID

    model_config = ConfigDict(from_attributes=True)
