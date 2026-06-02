"""MySQL connector — live SQL pushdown via aiomysql."""

from __future__ import annotations

import asyncio
from typing import Any

from ...errors import (
    ConnectorConnectionError,
    ConnectorError,
    MissingDependencyError,
    QueryExecutionError,
)
from ...models import (
    ConnectorCapabilities,
    ConnectorConfigEntrySchema,
    ConnectorConfigSchema,
    ConnectorPluginMetadata,
    ConnectorSyncStrategy,
    FieldType,
    LangbridgeCatalog,
)
from ...sql import SqlConnector
from .config import MySQLConnectorConfig

_TYPE_MAP: dict[str, FieldType] = {
    "tinyint": FieldType.INTEGER,
    "smallint": FieldType.INTEGER,
    "mediumint": FieldType.INTEGER,
    "int": FieldType.INTEGER,
    "integer": FieldType.INTEGER,
    "bigint": FieldType.INTEGER,
    "year": FieldType.INTEGER,
    "float": FieldType.FLOAT,
    "double": FieldType.FLOAT,
    "decimal": FieldType.FLOAT,
    "numeric": FieldType.FLOAT,
    "bit": FieldType.BOOLEAN,
    "bool": FieldType.BOOLEAN,
    "boolean": FieldType.BOOLEAN,
    "datetime": FieldType.TIMESTAMP,
    "timestamp": FieldType.TIMESTAMP,
    "date": FieldType.DATE,
    "binary": FieldType.BINARY,
    "varbinary": FieldType.BINARY,
    "blob": FieldType.BINARY,
    "tinyblob": FieldType.BINARY,
    "mediumblob": FieldType.BINARY,
    "longblob": FieldType.BINARY,
    "json": FieldType.JSON,
    "char": FieldType.STRING,
    "varchar": FieldType.STRING,
    "text": FieldType.STRING,
    "tinytext": FieldType.STRING,
    "mediumtext": FieldType.STRING,
    "longtext": FieldType.STRING,
    "enum": FieldType.STRING,
    "set": FieldType.STRING,
    "time": FieldType.STRING,
}


class MySQLConnector(SqlConnector[MySQLConnectorConfig]):
    """Connector for MySQL-compatible databases."""

    key = "mysql"
    dialect = "mysql"

    def __init__(self, config: MySQLConnectorConfig) -> None:
        super().__init__(config)
        self._pool: Any | None = None
        self._pool_lock = asyncio.Lock()

    @classmethod
    def get_config_schema(cls) -> ConnectorConfigSchema:
        return ConnectorConfigSchema(
            name="MySQL",
            description="Connect to a MySQL database and query it live via SQL pushdown.",
            version="1.0.0",
            config=[
                ConnectorConfigEntrySchema(field="host", label="Host", required=True, description="Database host address.", type="string"),
                ConnectorConfigEntrySchema(field="port", label="Port", required=False, default="3306", description="Database port.", type="number"),
                ConnectorConfigEntrySchema(field="database", label="Database", required=True, description="Database name.", type="string"),
                ConnectorConfigEntrySchema(field="user", label="User", required=True, description="Database user.", type="string"),
                ConnectorConfigEntrySchema(field="password", label="Password", required=True, description="Database password.", type="password", secret=True),
                ConnectorConfigEntrySchema(field="pool_size", label="Pool size", required=False, default="5", description="Maximum pooled connections.", type="number"),
            ],
            plugin_metadata=ConnectorPluginMetadata(
                default_sync_strategy=ConnectorSyncStrategy.INCREMENTAL,
                capabilities=ConnectorCapabilities(
                    supports_live_datasets=True,
                    supports_synced_datasets=True,
                    supports_incremental_sync=True,
                    supports_query_pushdown=True,
                    supports_preview=True,
                    supports_federated_execution=True,
                ),
            ),
        )

    async def connect(self) -> None:
        await self._get_pool()

    async def disconnect(self) -> None:
        if self._pool is not None:
            self._pool.close()
            await self._pool.wait_closed()
            self._pool = None

    async def get_catalog(self) -> LangbridgeCatalog:
        return await self._information_schema_catalog(
            schema=self.config.database,
            type_map=_TYPE_MAP,
            catalog_name="mysql",
            catalog_description=f"MySQL database '{self.config.database}'",
        )

    def _quote_identifier(self, name: str) -> str:
        return "`" + name.replace("`", "``") + "`"

    async def _get_pool(self) -> Any:
        if self._pool is not None:
            return self._pool
        async with self._pool_lock:
            if self._pool is None:
                try:
                    import aiomysql
                except ModuleNotFoundError as exc:
                    raise MissingDependencyError("mysql", "aiomysql", "mysql") from exc
                config = self.config
                try:
                    self._pool = await aiomysql.create_pool(
                        host=config.host,
                        port=config.port,
                        db=config.database,
                        user=config.user,
                        password=config.password,
                        autocommit=True,
                        minsize=1,
                        maxsize=config.pool_size,
                    )
                except Exception as exc:  # noqa: BLE001 - normalised below
                    raise ConnectorConnectionError(
                        f"Unable to connect to MySQL: {exc}"
                    ) from exc
        return self._pool

    async def _fetch(self, sql: str) -> tuple[list[str], list[tuple]]:
        pool = await self._get_pool()
        try:
            async with pool.acquire() as connection:
                async with connection.cursor() as cursor:
                    await cursor.execute(sql)
                    columns = [desc[0] for desc in (cursor.description or [])]
                    rows = [tuple(row) for row in await cursor.fetchall()]
                    return columns, rows
        except ConnectorError:
            raise
        except Exception as exc:  # noqa: BLE001 - normalised to connector error
            raise QueryExecutionError(f"MySQL query failed: {exc}") from exc
