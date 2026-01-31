import json
import logging
import uuid
from typing import Any, Dict, Optional, Type

from langbridge.packages.connectors.langbridge_connectors.api import (
    BaseConnectorConfig,
    BaseConnectorConfigFactory,
    BaseConnectorConfigSchemaFactory,
    ConnectorConfigSchema,
    ConnectorRuntimeType,
    ConnectorRuntimeTypeSqlDialectMap,
    ConnectorRuntimeTypeVectorDBMap,
    SqlConnector,
    SqlConnectorFactory,
    VecotorDBConnector,
    VectorDBConnectorFactory,
    get_connector_config_factory,
    get_connector_config_schema_factory,
)
from langbridge.packages.common.langbridge_common.db.auth import Organization
from langbridge.packages.common.langbridge_common.db.connector import DatabaseConnector
from langbridge.packages.common.langbridge_common.errors.application_errors import BusinessValidationError
from langbridge.packages.common.langbridge_common.contracts.connectors import ConnectorResponse, CreateConnectorRequest, UpdateConnectorRequest
from langbridge.packages.common.langbridge_common.repositories.connector_repository import ConnectorRepository
from langbridge.packages.common.langbridge_common.repositories.organization_repository import (
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
        self._vector_connector_factory = VectorDBConnectorFactory()
        self._logger = logging.getLogger(__name__)

    async def list_organization_connectors(
        self,
        organization_id: uuid.UUID,
    ) -> list[ConnectorResponse]:
        organization = await self._organization_repository.get_by_id(organization_id)
        if not organization:
            raise BusinessValidationError("Organization not found")
        return [
            ConnectorResponse.from_connector(connector, organization_id=organization_id)
            for connector in organization.connectors
        ]

    async def list_all_connectors(self) -> list[ConnectorResponse]:
        connectors = await self._connector_repository.get_all()
        return [ConnectorResponse.from_connector(connector) for connector in connectors]

    async def list_project_connectors(self, project_id: uuid.UUID) -> list[ConnectorResponse]:
        project = await self._project_repository.get_by_id(project_id)
        if not project:
            raise BusinessValidationError("Project not found")
        return [
            ConnectorResponse.from_connector(
                connector,
                organization_id=project.organization_id,
                project_id=project_id,
            )
            for connector in project.connectors
        ]

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

    @staticmethod
    def _build_config_instance(
        connector_type: ConnectorRuntimeType,
        connector_config: Dict[str, Any],
    ) -> BaseConnectorConfig:
        config_factory: Type[BaseConnectorConfigFactory] = get_connector_config_factory(
            connector_type
        )
        return config_factory.create(connector_config["config"])

    async def _validate_connector_config(
        self,
        connector_type: ConnectorRuntimeType,
        connector_config: Dict[str, Any],
    ) -> None:
        if connector_type in ConnectorRuntimeTypeSqlDialectMap:
            await self.async_create_sql_connector(connector_type, connector_config)
            return
        if connector_type in ConnectorRuntimeTypeVectorDBMap:
            await self.async_create_vector_connector(connector_type, connector_config)
            return
        raise BusinessValidationError(f"Unsupported connector type: {connector_type.value}")

    async def create_connector(self, create_request: CreateConnectorRequest) -> ConnectorResponse:
        connector_type = ConnectorRuntimeType(create_request.connector_type.upper())

        if not getattr(create_request, "config", None):
            raise BusinessValidationError("Connector config must be provided")

        config_json = json.dumps(create_request.config)

        try:
            await self._validate_connector_config(connector_type, create_request.config)
        except Exception as exc:
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
        dialect = ConnectorRuntimeTypeSqlDialectMap.get(connector_type)
        if dialect is None:
            raise BusinessValidationError(
                f"Connector type {connector_type.value} does not support SQL operations."
            )
        config_instance = self._build_config_instance(connector_type, connector_config)
        sql_connector = self._sql_connector_factory.create_sql_connector(
            dialect,
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
        dialect = ConnectorRuntimeTypeSqlDialectMap.get(connector_type)
        if dialect is None:
            raise BusinessValidationError(
                f"Connector type {connector_type.value} does not support SQL operations."
            )
        config_instance = self._build_config_instance(connector_type, connector_config)
        sql_connector = self._sql_connector_factory.create_sql_connector(
            dialect,
            config_instance,
            logger=self._logger,
        )
        await sql_connector.test_connection()
        return sql_connector

    async def create_vector_connector(
        self,
        connector_type: ConnectorRuntimeType,
        connector_config: Dict[str, Any],
    ) -> VecotorDBConnector:
        return await self.async_create_vector_connector(connector_type, connector_config)

    async def async_create_vector_connector(
        self,
        connector_type: ConnectorRuntimeType,
        connector_config: Dict[str, Any],
    ) -> VecotorDBConnector:
        vector_type = ConnectorRuntimeTypeVectorDBMap.get(connector_type)
        if vector_type is None:
            raise BusinessValidationError(
                f"Connector type {connector_type.value} is not configured as a vector database."
            )
        config_instance = self._build_config_instance(connector_type, connector_config)
        vector_connector = self._vector_connector_factory.create_vector_connector(
            vector_type,
            config_instance,
            logger=self._logger,
        )
        await vector_connector.test_connection()
        return vector_connector
