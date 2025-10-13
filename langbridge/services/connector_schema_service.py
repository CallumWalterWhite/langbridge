import json
from typing import Optional
from uuid import UUID
from connectors.config import BaseConnectorConfig, ConnectorType
from connectors.metadata import BaseMetadataExtractor, TableMetadata, ColumnMetadata, SchemaMetadata, get_metadata_extractor, build_connector_config
from db.connector import Connector
from errors.application_errors import BusinessValidationError
from repositories.connector_repository import ConnectorRepository

class ConnectorSchemaService:
    def __init__(self, connector_repository: ConnectorRepository) -> None:
        self._connector_repository = connector_repository

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

    def get_schemas(self, connector_id: str) -> list[str]:
        connector = self.__get_connector(UUID(connector_id))
        config = self.__get_connector_config(connector)
        extractor: BaseMetadataExtractor = get_metadata_extractor(ConnectorType(connector.connector_type))
        return extractor.fetch_schemas(config)
    
    def get_tables(self, connector_id: str, schema: str) -> list[str]:
        connector = self.__get_connector(UUID(connector_id))
        config = self.__get_connector_config(connector)
        extractor: BaseMetadataExtractor = get_metadata_extractor(ConnectorType(connector.connector_type))
        return extractor.fetch_tables(config)
    
    def get_columns(self, connector_id: str, schema: str, table: str) -> list[ColumnMetadata]:
        connector = self.__get_connector(UUID(connector_id))
        config = self.__get_connector_config(connector)
        extractor: BaseMetadataExtractor = get_metadata_extractor(ConnectorType(connector.connector_type))
        return extractor.fetch_columns(config)