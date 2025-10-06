import json
from sqlalchemy.orm import Session
from db.auth import Organization, Project
from db.connector import Connector
from errors.application_errors import BusinessValidationError
from repositories.connector_repository import ConnectorRepository
from repositories.organization_repository import OrganizationRepository, ProjectRepository
from schemas.connectors import CreateConnectorRequest, UpdateConnectorRequest


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

    def list_organization_connectors(self, organization: Organization) -> list[Connector]:
        return organization.connectors

    def list_project_connectors(self, project: Project) -> list[Connector]:
        return project.connectors
        
    def create_connector(
        self, create_request: CreateConnectorRequest
    ) -> Connector:
        config_json: str
        if hasattr(create_request, "config_json") and create_request.config_json is not None:
            # Already a string on the DTO
            config_json = create_request.config_json
        elif hasattr(create_request, "config") and create_request.config is not None:
            # Likely a dict on the DTO, serialize it
            config_json = json.dumps(create_request.config)
        else:
            raise BusinessValidationError("Connector config must be provided")
        
        connector = Connector(
            name=create_request.name,
            type=create_request.connector_type,
            config_json=config_json,
            description=create_request.description,
        )
        
        if create_request.organization_id is None and create_request.project_id is None:
            raise BusinessValidationError("Either organization_id or project_id must be provided")
        
        if create_request.organization_id:
            organization: Organization = self._organization_repository.get_by_id(create_request.organization_id)
            if not organization:
                raise BusinessValidationError("Organization not found")
            organization.connectors.append(connector)
        
        if create_request.project_id:
            project: Project = self._project_repository.get_by_id(create_request.project_id)
            if not project:
                raise BusinessValidationError("Project not found")
            project.connectors.append(connector)
            if create_request.organization_id and project.organization_id != create_request.organization_id:
                raise BusinessValidationError("Project does not belong to the specified organization")
            if create_request.organization_id is None:
                organization = self._organization_repository.get_by_id(project.organization_id)
                organization.connectors.append(connector)
        
        self._connector_repository.add(connector)
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
    