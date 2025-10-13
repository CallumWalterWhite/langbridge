
from typing import Dict, List
from connectors.config import (
    BaseConnectorConfig, ConnectorType
)
from connectors.metadata import (
    BaseMetadataExtractor, 
    ColumnMetadata, 
    TableMetadata
)
from errors.application_errors import BusinessValidationError

from .config import SqliteConnectorConfig

from sqlite3 import Cursor, connect, OperationalError, DatabaseError, ProgrammingError

class SqliteMetadataExtractor(BaseMetadataExtractor):
    type = ConnectorType.SQLITE

    def __create_cursor(self, config: SqliteConnectorConfig) -> Cursor:
        try:
            conn = connect(config.location)
        except (ProgrammingError, OperationalError, DatabaseError) as exc:
            raise BusinessValidationError(f"Unable to connect to Sqlite: {exc}") from exc

        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        return cursor

    def fetch_schemas(self, _: SqliteConnectorConfig) -> List[str]:
        return ["main"]
    
    def fetch_tables(self, config: SqliteConnectorConfig) -> List[str]:
        cursor = self.__create_cursor(config)
        conn = cursor.connection
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            return [row[0] for row in cursor.fetchall()]
        finally:
            cursor.close()
            conn.close()

    def fetch_columns(self, config: SqliteConnectorConfig) -> List[ColumnMetadata]:
        cursor = self.__create_cursor(config)
        conn = cursor.connection
        try:
            cursor.execute("PRAGMA table_info(main)")
            return [ColumnMetadata(name=row[1], data_type=row[2]) for row in cursor.fetchall()]
        finally:
            cursor.close()
            conn.close()

    def fetch_metadata(self, config: SqliteConnectorConfig) -> List[TableMetadata]:

        tables: Dict[tuple[str, str], List[ColumnMetadata]] = {}
        cursor = self.__create_cursor(config)
        conn = cursor.connection
        try:
            base_query = """
                SELECT
                    table_schema AS schema_name,
                    table_name,
                    column_name,
                    data_type
                FROM
                    information_schema.columns
                WHERE
                    table_schema NOT IN ('pg_catalog', 'information_schema')
                ORDER BY
                    table_schema,
                    table_name,
                    ordinal_position
            """

            cursor.execute(base_query)
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