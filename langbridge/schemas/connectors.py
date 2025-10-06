from typing import Any, Dict, Optional
from uuid import UUID

from .base import _Base


class ConnectorResponse(_Base):
    id: Optional[UUID] = None
    name: str
    description: Optional[str] = None
    version: Optional[str] = None
    label: Optional[str] = None
    icon: Optional[str] = None
    connector_type: Optional[str] = None
    organization_id: Optional[UUID] = None
    project_id: Optional[UUID] = None
    config: Optional[Dict[str, Any]] = None
    
class CreateConnectorRequest(_Base):
    name: str
    description: Optional[str] = None
    version: Optional[str] = None
    label: Optional[str] = None
    icon: Optional[str] = None
    connector_type: Optional[str] = None
    organization_id: Optional[UUID] = None
    project_id: Optional[UUID] = None
    config: Optional[Dict[str, Any]] = None
    
class UpdateConnectorRequest(_Base):
    name: Optional[str] = None
    description: Optional[str] = None
    version: Optional[str] = None
    label: Optional[str] = None
    icon: Optional[str] = None
    connector_type: Optional[str] = None
    organization_id: Optional[UUID] = None
    project_id: Optional[UUID] = None
    config: Optional[Dict[str, Any]] = None