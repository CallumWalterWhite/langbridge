import json
from typing import Any, Dict, Optional, Type, Union
import logging
import uuid
from sqlalchemy.orm import Session
from db.auth import Organization, Project
from db.connector import Connector, DatabaseConnector
from errors.application_errors import BusinessValidationError
from repositories.connector_repository import ConnectorRepository
from repositories.organization_repository import OrganizationRepository, ProjectRepository
from schemas.connectors import CreateConnectorRequest, UpdateConnectorRequest

from connectors import (
    SqlConnectorFactory, 
    SqlConnector,
    ConnectorRuntimeType,
    get_connector_config_schema_factory, 
    get_connector_config_factory,
    ConnectorConfigSchema, 
    BaseConnectorConfig,
    BaseConnectorConfigFactory, 
    BaseConnectorConfigSchemaFactory,
    ConnectorRuntimeTypeSqlDialectMap
)

class ConnectorService:
    """Domain logic for managing connectors."""
    
    def __init__(
        self,
        connector_repository: ConnectorRepository,
        organization_repository: OrganizationRepository,
        project_repository: ProjectRepository
    ) -> None:
        self._connector_repository = connector_repository
        self._organization_repository = organization_repository
        self._project_repository = project_repository
        self._sql_connector_factory = SqlConnectorFactory()
        self._logger = logging.getLogger(__name__)

    def list_organization_connectors(self, organization: Organization) -> list[Connector]:
        return organization.connectors

    def list_project_connectors(self, project: Project) -> list[Connector]:
        return project.connectors
    
    def list_connector_types(self) -> list[str]:
        return [ct.value for ct in ConnectorRuntimeType]
    
    def get_connector_config_schema(self, connector_type: str) -> ConnectorConfigSchema:
        try:
            connector_type_enum: ConnectorRuntimeType = ConnectorRuntimeType(connector_type.upper())
            config_schema_factory: Type[BaseConnectorConfigSchemaFactory] = get_connector_config_schema_factory(connector_type_enum)
            return config_schema_factory.create({})
        except ValueError as e:
            raise BusinessValidationError(str(e))
        
    def create_connector(
        self, create_request: CreateConnectorRequest
    ) -> Connector:
        connector_type: ConnectorRuntimeType = ConnectorRuntimeType(create_request.connector_type.upper())
        config_json: str
        connector_config: Dict[str, Any]
        if hasattr(create_request, "config") and create_request.config is not None:
            connector_config = create_request.config
            config_json = json.dumps(connector_config)
        else:
            raise BusinessValidationError("Connector config must be provided")
        
        # TOOD: handle other connector types
        # Currently only database connectors are supported
        try:
            _ = self.__create_sql_connector(connector_type, connector_config)
        except Exception as e:
            raise BusinessValidationError(str(e))
        
        connector: DatabaseConnector = DatabaseConnector( #TODO: handle other connector types
            id=uuid.uuid4(),
            name=create_request.name,
            type="database_connector",
            connector_type=connector_type.value,
            config_json=config_json,
            description=create_request.description,
        )
        
        self._connector_repository.add(connector)
        
        if create_request.organization_id is None and create_request.project_id is None:
            raise BusinessValidationError("Either organization_id or project_id must be provided")
        
        organization: Optional[Organization] = self._organization_repository.get_by_id(create_request.organization_id)
        if not organization:
            raise BusinessValidationError("Organization not found")
        organization.connectors.append(connector)
        
        if create_request.project_id:
            project: Optional[Project] = self._project_repository.get_by_id(create_request.project_id)
            if not project:
                raise BusinessValidationError("Project not found")
            project.connectors.append(connector)
            if create_request.organization_id and project.organization_id != create_request.organization_id:
                raise BusinessValidationError("Project does not belong to the specified organization")
            if create_request.organization_id is None:
                organization = self._organization_repository.get_by_id(project.organization_id)
                organization.connectors.append(connector)
        
        return connector

    def get_connector(self, connector_id: str) -> Connector:
        connector = self._connector_repository.get_by_id(connector_id)
        if not connector:
            raise BusinessValidationError("Connector not found")
        return connector

    def update_connector(self, connector_id: str, update_request: UpdateConnectorRequest) -> Connector:
        connector: Connector = self.get_connector(connector_id)
        for field in ["name", "description", "version", "label", "icon", "connector_type", "config"]:
            value = getattr(update_request, field, None)
            if value is not None:
                setattr(connector, field, value)
        return connector

    def delete_connector(self, connector_id: str) -> None:
        connector: Connector = self.get_connector(connector_id)
        self._connector_repository.delete(connector)
    
    
    def __create_sql_connector(self, 
                                connector_type: ConnectorRuntimeType,
                                connector_config: Dict[str, Any]) -> SqlConnector:
        
        config_factory: Type[BaseConnectorConfigFactory] = get_connector_config_factory(connector_type)
        config_instance: BaseConnectorConfig = config_factory.create(connector_config["config"])
        sql_connector: SqlConnector = self._sql_connector_factory.create_sql_connector(
            ConnectorRuntimeTypeSqlDialectMap[connector_type],
            config_instance,
            logger=self._logger
        )
        sql_connector.test_connection_sync()
        return sql_connector