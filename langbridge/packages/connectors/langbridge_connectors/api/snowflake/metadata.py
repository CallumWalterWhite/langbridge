
from typing import Dict, List
from langbridge.packages.connectors.langbridge_connectors.api.config import (
    BaseConnectorConfig, ConnectorRuntimeType
)
from langbridge.packages.connectors.langbridge_connectors.api.metadata import (
    BaseMetadataExtractor, 
    ColumnMetadata, 
    TableMetadata
)
from langbridge.packages.common.langbridge_common.errors.application_errors import BusinessValidationError

from .config import SnowflakeConnectorConfig

from snowflake.connector import ProgrammingError, OperationalError, DatabaseError, connect

class SnowflakeMetadataExtractor(BaseMetadataExtractor):
    type = ConnectorRuntimeType.SNOWFLAKE

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
            cursor.execute("USE DATABASE {}".format(config.database))
            base_query = """
                SELECT table_schema, table_name, column_name, data_type
                FROM information_schema.columns
            """
            params: List[str] = []
            if config.schema:
                base_query += " WHERE table_schema = %s"
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
            TableMetadata(schema=schema, name=table)
            for (schema, table), columns in tables.items()
        ]