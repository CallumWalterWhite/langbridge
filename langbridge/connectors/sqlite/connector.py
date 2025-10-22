import logging
from typing import Optional
from connectors.base import SqlConnector
from connectors.config import BaseConnectorConfig
from connectors import SqlDialetcs
from errors.connector_errors import ConnectorError
from connectors.metadata import ColumnMetadata
from .config import SqliteConnectorConfig
from sqlite3 import connect, OperationalError, DatabaseError, ProgrammingError

class SqliteConnector(SqlConnector):
    """
    SQLite connector implementation.
    """
    
    SQL_DIALECT: SqlDialetcs = SqlDialetcs.SQLITE

    def __init__(
        self,
        config: SqliteConnectorConfig,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        super().__init__(config=config, logger=logger)
        self.database_path = config.location
        
        
    def test_connection(self) -> None:
        try:
            conn = connect(self.database_path)
            conn.close()
        except (ProgrammingError, OperationalError, DatabaseError) as exc:
            self.logger.error("Connection test failed: %s", exc)
            raise ConnectorError(f"Unable to connect to SQLite database: {exc}") from exc
        
    def fetch_schemas(self) -> list[str]:
        return ["main"]
    
    def fetch_tables(self) -> list[str]:
        try:
            conn = connect(self.database_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            cursor.close()
            conn.close()
            return tables
        except (ProgrammingError, OperationalError, DatabaseError) as exc:
            self.logger.error("Failed to fetch tables: %s", exc)
            raise ConnectorError(f"Unable to fetch tables from SQLite database: {exc}") from exc
        
    def fetch_columns(self) -> list[ColumnMetadata]:
        try:
            conn = connect(self.database_path)
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(main)")
            columns = [ColumnMetadata(name=row[1], data_type=row[2]) for row in cursor.fetchall()]
            cursor.close()
            conn.close()
            return columns
        except (ProgrammingError, OperationalError, DatabaseError) as exc:
            self.logger.error("Failed to fetch columns: %s", exc)
            raise ConnectorError(f"Unable to fetch columns from SQLite database: {exc}") from exc
        
        
    async def _execute_select(
        self,
        sql: str,
        params: dict[str, any],
        *,
        timeout_s: Optional[int] = 30,
    ) -> tuple[list[str], list[tuple]]:
        try:
            conn = connect(self.database_path)
            cursor = conn.cursor()
            cursor.execute(sql, params)
            columns = [description[0] for description in cursor.description]
            rows = cursor.fetchall()
            cursor.close()
            conn.close()
            return columns, rows
        except (ProgrammingError, OperationalError, DatabaseError) as exc:
            self.logger.error("SQL execution failed: %s", exc)
            raise ConnectorError(f"SQL execution failed on SQLite database: {exc}") from exc