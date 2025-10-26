from typing import Any, Dict, Optional, cast
from uuid import UUID
import json

from db.connector import Connector

from .base import _Base


class ConnectorResponse(_Base):
    id: Optional[UUID] = None
    name: str
    description: Optional[str] = None
    version: Optional[str] = None
    label: Optional[str] = None
    icon: Optional[str] = None
    connector_type: Optional[str] = None
    organization_id: UUID
    project_id: Optional[UUID] = None
    config: Optional[Dict[str, Any]] = None
    @staticmethod
    def from_connector(connector: Connector) -> "ConnectorResponse":
        raw_config = connector.config_json
        config: Optional[Dict[str, Any]] = None
        if isinstance(raw_config, (str, bytes)):
            try:
                config = json.loads(raw_config)
            except Exception:
                config = None
        elif isinstance(raw_config, dict):
            config = raw_config

        return ConnectorResponse(
            id=cast(Optional[UUID], connector.id),
            name=cast(str, connector.name),
            description=cast(Optional[str], connector.description),
            version="", # TODO: implement
            label=cast(Optional[str], connector.name),
            icon="", # TODO: implement
            connector_type=cast(Optional[str], connector.connector_type),
            organization_id=cast(UUID, connector.organizations[0].id),
            project_id=None,
            config=config,
        )
    
class CreateConnectorRequest(_Base):
    name: str
    description: Optional[str] = None
    version: Optional[str] = None
    label: Optional[str] = None
    connector_type: str
    organization_id: UUID
    project_id: Optional[UUID] = None
    config: Optional[Dict[str, Any]] = None
    
class UpdateConnectorRequest(_Base):
    name: Optional[str] = None
    description: Optional[str] = None
    version: Optional[str] = None
    label: Optional[str] = None
    icon: Optional[str] = None
    connector_type: Optional[str] = None
    organization_id: UUID
    project_id: Optional[UUID] = None
    config: Optional[Dict[str, Any]] = None

class ConnectorListResponse(_Base):
    connectors: list[ConnectorResponse] = []

class ConnectorSourceSchemasResponse(_Base):
    schemas: list[str] = []

class ConnectorSourceSchemaResponse(_Base):
    schema: str
    tables: list[str]

class ConnectorSourceSchemaColumnResponse(_Base):
    name: str
    type: str
    nullable: Optional[bool] = None
    primary_key: Optional[bool] = False

class ConnectorSourceSchemaTableResponse(_Base):
    name: str
    columns: Dict[str, ConnectorSourceSchemaColumnResponse] = {}
    
class ConnectorSourceSchemaViewResponse(_Base):
    name: str
    columns: Dict[str, ConnectorSourceSchemaColumnResponse] = {}
    definition: str
