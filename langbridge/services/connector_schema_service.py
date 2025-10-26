import json
import logging
from uuid import UUID
from connectors.config import BaseConnectorConfig, ConnectorType
from db.connector import Connector
from errors.application_errors import BusinessValidationError
from repositories.connector_repository import ConnectorRepository


from connectors import (
    SqlConnectorFactory, 
    SqlConnector,
    build_connector_config,
    ColumnMetadata,
    BaseConnectorConfig,
    ConnectorRuntimeTypeSqlDialectMap
)

class ConnectorSchemaService:
    def __init__(self, connector_repository: ConnectorRepository) -> None:
        self._connector_repository = connector_repository
        self._sql_connector_factory = SqlConnectorFactory()
        self._logger = logging.getLogger(__name__)

    def __get_connector(self, connector_id: UUID) -> Connector:
        connector: Connector | None = self._connector_repository.get_by_id(connector_id)
        if not connector:
            raise BusinessValidationError("Connector not found")
        return connector
    
    def __get_connector_config(self, connector: Connector) -> BaseConnectorConfig:
        config_payload = json.loads(connector.config_json if isinstance(connector.config_json, str) else connector.config_json.value)
        if hasattr(config_payload, "to_dict"):
            config_payload = config_payload.to_dict()
        config: BaseConnectorConfig = build_connector_config(ConnectorType(connector.connector_type), config_payload)
        return config
    
    def __get_sql_connector(self, connector: Connector) -> SqlConnector:
        connector_config: BaseConnectorConfig = self.__get_connector_config(connector)
        sql_connector: SqlConnector = self._sql_connector_factory.create_sql_connector(
            ConnectorRuntimeTypeSqlDialectMap[ConnectorType(connector.connector_type)],
            connector_config,
            logger=self._logger
        )
        sql_connector.test_connection_sync()
        return sql_connector

    def get_schemas(self, connector_id: str) -> list[str]:
        connector = self.__get_connector(UUID(connector_id))
        sql_connector = self.__get_sql_connector(connector)
        return sql_connector.fetch_schemas_sync()
    
    def get_tables(self, connector_id: str, schema: str) -> list[str]:
        connector = self.__get_connector(UUID(connector_id))
        sql_connector = self.__get_sql_connector(connector)
        return sql_connector.fetch_tables_sync(schema=schema)
    
    def get_columns(self, connector_id: str, schema: str, table: str) -> list[ColumnMetadata]:
        connector = self.__get_connector(UUID(connector_id))
        sql_connector = self.__get_sql_connector(connector)
        return sql_connector.fetch_columns_sync(schema=schema, table=table)