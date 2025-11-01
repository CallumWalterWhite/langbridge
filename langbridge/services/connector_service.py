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
from repositories.connector_repository import ConnectorRepository
from repositories.organization_repository import (
    OrganizationRepository,
    ProjectRepository,
)
from schemas.connectors import CreateConnectorRequest, UpdateConnectorRequest


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

    def list_organization_connectors(self, organization: Organization) -> list[Connector]:
        return organization.connectors

    async def list_all_connectors(self) -> list[Connector]:
        return await self._connector_repository.get_all()

    def list_project_connectors(self, project: Project) -> list[Connector]:
        return project.connectors

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

    async def create_connector(self, create_request: CreateConnectorRequest) -> Connector:
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

        return connector

    async def get_connector(self, connector_id: str) -> Connector:
        connector = await self._connector_repository.get_by_id(connector_id)
        if not connector:
            raise BusinessValidationError("Connector not found")
        return connector

    async def update_connector(
        self,
        connector_id: str,
        update_request: UpdateConnectorRequest,
    ) -> Connector:
        connector = await self.get_connector(connector_id)
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
                setattr(connector, field, value)
        return connector

    async def delete_connector(self, connector_id: str) -> None:
        connector = await self.get_connector(connector_id)
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
