import json
import logging
import uuid
from typing import Any, Dict, Optional, Type

from connectors import (
    BaseConnectorConfig,
    BaseConnectorConfigFactory,
    BaseConnectorConfigSchemaFactory,
    ConnectorConfigSchema,
    ConnectorRuntimeType,
    ConnectorRuntimeTypeSqlDialectMap,
    SqlConnector,
    SqlConnectorFactory,
    get_connector_config_factory,
    get_connector_config_schema_factory,
)
from db.auth import Organization, Project
from db.connector import Connector, DatabaseConnector
from errors.application_errors import BusinessValidationError
from models.connectors import ConnectorResponse, CreateConnectorRequest, UpdateConnectorRequest
from repositories.connector_repository import ConnectorRepository
from repositories.organization_repository import (
    OrganizationRepository,
    ProjectRepository,
)


class ConnectorService:
    """Domain logic for managing connectors."""

    def __init__(
        self,
        connector_repository: ConnectorRepository,
        organization_repository: OrganizationRepository,
        project_repository: ProjectRepository,
    ) -> None:
        self._connector_repository = connector_repository
        self._organization_repository = organization_repository
        self._project_repository = project_repository
        self._sql_connector_factory = SqlConnectorFactory()
        self._logger = logging.getLogger(__name__)

    async def list_organization_connectors(
        self,
        organization_id: uuid.UUID,
    ) -> list[ConnectorResponse]:
        organization = await self._organization_repository.get_by_id(organization_id)
        if not organization:
            raise BusinessValidationError("Organization not found")
        return [ConnectorResponse.from_connector(connector) for connector in organization.connectors]

    async def list_all_connectors(self) -> list[ConnectorResponse]:
        connectors = await self._connector_repository.get_all()
        return [ConnectorResponse.from_connector(connector) for connector in connectors]

    async def list_project_connectors(self, project_id: uuid.UUID) -> list[ConnectorResponse]:
        project = await self._project_repository.get_by_id(project_id)
        if not project:
            raise BusinessValidationError("Project not found")
        return [ConnectorResponse.from_connector(connector) for connector in project.connectors]

    def list_connector_types(self) -> list[str]:
        return [ct.value for ct in ConnectorRuntimeType]

    def get_connector_config_schema(self, connector_type: str) -> ConnectorConfigSchema:
        try:
            connector_type_enum = ConnectorRuntimeType(connector_type.upper())
            factory: Type[BaseConnectorConfigSchemaFactory] = (
                get_connector_config_schema_factory(connector_type_enum)
            )
            return factory.create({})
        except ValueError as exc:
            raise BusinessValidationError(str(exc)) from exc

    async def create_connector(self, create_request: CreateConnectorRequest) -> ConnectorResponse:
        connector_type = ConnectorRuntimeType(create_request.connector_type.upper())

        if not getattr(create_request, "config", None):
            raise BusinessValidationError("Connector config must be provided")

        config_json = json.dumps(create_request.config)

        try:
            _ = await self.create_sql_connector(connector_type, create_request.config)
        except Exception as exc:  # pragma: no cover - defensive conversion
            raise BusinessValidationError(str(exc)) from exc

        connector = DatabaseConnector(
            id=uuid.uuid4(),
            name=create_request.name,
            type="database_connector",
            connector_type=connector_type.value,
            config_json=config_json,
            description=create_request.description,
        )

        self._connector_repository.add(connector)
        # await self._connector_repository.commit()

        if create_request.organization_id is None and create_request.project_id is None:
            raise BusinessValidationError(
                "Either organization_id or project_id must be provided"
            )

        organization: Optional[Organization] = None
        if create_request.organization_id is not None:
            organization = await self._organization_repository.get_by_id(
                create_request.organization_id
            )
            if not organization:
                raise BusinessValidationError("Organization not found")
        organization.connectors.append(connector)
        # await self._organization_repository.commit()

        if create_request.project_id:
            project = await self._project_repository.get_by_id(create_request.project_id)
            if not project:
                raise BusinessValidationError("Project not found")

            if (
                create_request.organization_id
                and project.organization_id != create_request.organization_id
            ):
                raise BusinessValidationError(
                    "Project does not belong to the specified organization"
                )

            project.connectors.append(connector)
            # await self._project_repository.commit()

            if organization is None:
                organization = await self._organization_repository.get_by_id(
                    project.organization_id
                )
                if not organization:
                    raise BusinessValidationError("Organization not found")
                organization.connectors.append(connector)
                # await self._organization_repository.commit()

        return ConnectorResponse.from_connector(connector)

    async def get_connector(self, connector_id: uuid.UUID) -> ConnectorResponse:
        connector = await self._connector_repository.get_by_id(connector_id)
        if not connector:
            raise BusinessValidationError("Connector not found")
        return ConnectorResponse.from_connector(connector)

    async def update_connector(
        self,
        connector_id: str,
        update_request: UpdateConnectorRequest,
    ) -> ConnectorResponse:
        connector_entity = await self._connector_repository.get_by_id(connector_id)
        if not connector_entity:
            raise BusinessValidationError("Connector not found")
        for field in [
            "name",
            "description",
            "version",
            "label",
            "icon",
            "connector_type",
            "config",
        ]:
            value = getattr(update_request, field, None)
            if value is not None:
                setattr(connector_entity, field, value)
        return ConnectorResponse.from_connector(connector_entity)

    async def delete_connector(self, connector_id: uuid.UUID) -> None:
        connector = await self._connector_repository.get_by_id(connector_id)
        if not connector:
            raise BusinessValidationError("Connector not found")
        await self._connector_repository.delete(connector)

    async def create_sql_connector(
        self,
        connector_type: ConnectorRuntimeType,
        connector_config: Dict[str, Any],
    ) -> SqlConnector:
        config_factory: Type[BaseConnectorConfigFactory] = get_connector_config_factory(
            connector_type
        )
        config_instance: BaseConnectorConfig = config_factory.create(
            connector_config["config"]
        )
        sql_connector = self._sql_connector_factory.create_sql_connector(
            ConnectorRuntimeTypeSqlDialectMap[connector_type],
            config_instance,
            logger=self._logger,
        )
        await sql_connector.test_connection()
        return sql_connector

    async def async_create_sql_connector(
        self,
        connector_type: ConnectorRuntimeType,
        connector_config: Dict[str, Any],
    ) -> SqlConnector:
        config_factory: Type[BaseConnectorConfigFactory] = get_connector_config_factory(
            connector_type
        )
        config_instance: BaseConnectorConfig = config_factory.create(
            connector_config["config"]
        )
        sql_connector = self._sql_connector_factory.create_sql_connector(
            ConnectorRuntimeTypeSqlDialectMap[connector_type],
            config_instance,
            logger=self._logger,
        )
        await sql_connector.test_connection()
        return sql_connector
