from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List

from snowflake.connector import ProgrammingError, OperationalError, DatabaseError, connect

from .config import (
    BaseConnectorConfig,
    BaseConnectorConfigFactory,
    ConnectorType,
    get_connector_config_factory,
)
from errors.application_errors import BusinessValidationError
from .snowflake.config import SnowflakeConnectorConfig

logger = logging.getLogger(__name__)


@dataclass
class ColumnMetadata:
    name: str
    data_type: str


@dataclass
class TableMetadata:
    schema: str
    name: str
    columns: List[ColumnMetadata]


class BaseMetadataExtractor(ABC):
    type: ConnectorType

    @abstractmethod
    def fetch_metadata(self, config: BaseConnectorConfig) -> List[TableMetadata]:
        raise NotImplementedError


class SnowflakeMetadataExtractor(BaseMetadataExtractor):
    type = ConnectorType.SNOWFLAKE

    def fetch_metadata(self, config: BaseConnectorConfig) -> List[TableMetadata]:
        if not isinstance(config, SnowflakeConnectorConfig):
            raise BusinessValidationError("Invalid Snowflake configuration provided.")

        try:
            conn = connect(
                user=config.user,
                password=config.password,
                account=config.account,
                database=config.database,
                warehouse=config.warehouse,
                schema=config.schema,
                role=config.role,
            )
        except (ProgrammingError, OperationalError, DatabaseError) as exc:
            raise BusinessValidationError(f"Unable to connect to Snowflake: {exc}") from exc

        tables: Dict[tuple[str, str], List[ColumnMetadata]] = {}
        cursor = conn.cursor()
        try:
            base_query = """
                SELECT table_schema, table_name, column_name, data_type
                FROM information_schema.columns
                WHERE table_catalog = %s
            """
            params: List[str] = [config.database]
            if config.schema:
                base_query += " AND table_schema = %s"
                params.append(config.schema)

            cursor.execute(base_query, params)
            for schema_name, table_name, column_name, data_type in cursor.fetchall():
                key = (schema_name, table_name)
                tables.setdefault(key, []).append(
                    ColumnMetadata(name=column_name, data_type=data_type)
                )
        finally:
            cursor.close()
            conn.close()

        return [
            TableMetadata(schema=schema, name=table, columns=columns)
            for (schema, table), columns in tables.items()
        ]


def get_metadata_extractor(connector_type: ConnectorType) -> BaseMetadataExtractor:
    for subclass in BaseMetadataExtractor.__subclasses__():
        if subclass.type == connector_type:
            return subclass()
    raise BusinessValidationError(f"No metadata extractor found for connector type '{connector_type.value}'.")


def build_connector_config(connector_type: ConnectorType, config_payload: dict) -> BaseConnectorConfig:
    factory: BaseConnectorConfigFactory = get_connector_config_factory(connector_type)
    return factory.create(config_payload)
