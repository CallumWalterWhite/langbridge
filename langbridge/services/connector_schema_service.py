import json
import logging
from uuid import UUID

from connectors import (
    BaseConnectorConfig,
    ColumnMetadata,
    ConnectorRuntimeTypeSqlDialectMap,
    SqlConnector,
    SqlConnectorFactory,
    build_connector_config,
)
from connectors.config import ConnectorType
from db.connector import Connector
from errors.application_errors import BusinessValidationError
from repositories.connector_repository import ConnectorRepository


class ConnectorSchemaService:
    def __init__(self, connector_repository: ConnectorRepository) -> None:
        self._connector_repository = connector_repository
        self._sql_connector_factory = SqlConnectorFactory()
        self._logger = logging.getLogger(__name__)

    async def _get_connector(self, connector_id: UUID) -> Connector:
        connector = await self._connector_repository.get_by_id(connector_id)
        if not connector:
            raise BusinessValidationError("Connector not found")
        return connector

    def _build_connector_config(self, connector: Connector) -> BaseConnectorConfig:
        payload = connector.config_json
        config_payload = json.loads(payload if isinstance(payload, str) else payload.value)
        if hasattr(config_payload, "to_dict"):
            config_payload = config_payload.to_dict()
        connector_type = ConnectorType(connector.connector_type)
        return build_connector_config(connector_type, config_payload["config"])

    async def _create_sql_connector(
        self,
        connector_type: ConnectorType,
        config: BaseConnectorConfig,
    ) -> SqlConnector:
        sql_connector = self._sql_connector_factory.create_sql_connector(
            ConnectorRuntimeTypeSqlDialectMap[connector_type],
            config,
            logger=self._logger,
        )
        await sql_connector.test_connection()
        return sql_connector

    async def _get_sql_connector(self, connector_id: UUID) -> SqlConnector:
        connector = await self._get_connector(connector_id)
        connector_type = ConnectorType(connector.connector_type)
        config = self._build_connector_config(connector)
        return await self._create_sql_connector(connector_type, config)

    async def get_schemas(self, connector_id: str) -> list[str]:
        sql_connector = await self._get_sql_connector(UUID(connector_id))
        return sql_connector.fetch_schemas_sync()

    async def get_tables(self, connector_id: str, schema: str) -> list[str]:
        sql_connector = await self._get_sql_connector(UUID(connector_id))
        return sql_connector.fetch_tables_sync(schema=schema)

    async def get_columns(
        self,
        connector_id: str,
        schema: str,
        table: str,
    ) -> list[ColumnMetadata]:
        sql_connector = await self._get_sql_connector(UUID(connector_id))
        return sql_connector.fetch_columns_sync(schema=schema, table=table)
