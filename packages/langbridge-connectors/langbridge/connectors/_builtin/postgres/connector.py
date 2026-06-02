"""PostgreSQL connector — live SQL pushdown via asyncpg."""

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
from .config import PostgresConnectorConfig

_TYPE_MAP: dict[str, FieldType] = {
    "smallint": FieldType.INTEGER,
    "integer": FieldType.INTEGER,
    "bigint": FieldType.INTEGER,
    "smallserial": FieldType.INTEGER,
    "serial": FieldType.INTEGER,
    "bigserial": FieldType.INTEGER,
    "real": FieldType.FLOAT,
    "double precision": FieldType.FLOAT,
    "numeric": FieldType.FLOAT,
    "decimal": FieldType.FLOAT,
    "money": FieldType.FLOAT,
    "boolean": FieldType.BOOLEAN,
    "timestamp without time zone": FieldType.TIMESTAMP,
    "timestamp with time zone": FieldType.TIMESTAMP,
    "date": FieldType.DATE,
    "bytea": FieldType.BINARY,
    "json": FieldType.JSON,
    "jsonb": FieldType.JSON,
    "text": FieldType.STRING,
    "character varying": FieldType.STRING,
    "character": FieldType.STRING,
    "uuid": FieldType.STRING,
}


class PostgresConnector(SqlConnector[PostgresConnectorConfig]):
    """Connector for PostgreSQL-compatible databases."""

    key = "postgres"
    dialect = "postgres"

    def __init__(self, config: PostgresConnectorConfig) -> None:
        super().__init__(config)
        self._pool: Any | None = None
        self._pool_lock = asyncio.Lock()

    @classmethod
    def get_config_schema(cls) -> ConnectorConfigSchema:
        return ConnectorConfigSchema(
            name="PostgreSQL",
            description="Connect to a PostgreSQL database and query it live via SQL pushdown.",
            version="1.0.0",
            config=[
                ConnectorConfigEntrySchema(field="host", label="Host", required=True, description="Database host address.", type="string"),
                ConnectorConfigEntrySchema(field="port", label="Port", required=False, default="5432", description="Database port.", type="number"),
                ConnectorConfigEntrySchema(field="database", label="Database", required=True, description="Database name.", type="string"),
                ConnectorConfigEntrySchema(field="user", label="User", required=True, description="Database user.", type="string"),
                ConnectorConfigEntrySchema(field="password", label="Password", required=True, description="Database password.", type="password", secret=True),
                ConnectorConfigEntrySchema(field="schema", label="Schema", required=False, default="public", description="Schema to introspect for the catalog.", type="string"),
                ConnectorConfigEntrySchema(
                    field="ssl",
                    label="SSL mode",
                    required=False,
                    description="Optional SSL mode.",
                    type="string",
                    value_list=["disable", "allow", "prefer", "require", "verify-ca", "verify-full"],
                ),
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
            await self._pool.close()
            self._pool = None

    async def get_catalog(self) -> LangbridgeCatalog:
        return await self._information_schema_catalog(
            schema=self.config.schema_,
            type_map=_TYPE_MAP,
            catalog_name="postgres",
            catalog_description=f"PostgreSQL database '{self.config.database}'",
        )

    async def _get_pool(self) -> Any:
        if self._pool is not None:
            return self._pool
        async with self._pool_lock:
            if self._pool is None:
                try:
                    import asyncpg
                except ModuleNotFoundError as exc:
                    raise MissingDependencyError("postgres", "asyncpg", "postgres") from exc
                config = self.config
                try:
                    self._pool = await asyncpg.create_pool(
                        host=config.host,
                        port=config.port,
                        database=config.database,
                        user=config.user,
                        password=config.password,
                        ssl=config.ssl,
                        min_size=1,
                        max_size=config.pool_size,
                    )
                except Exception as exc:  # noqa: BLE001 - normalised below
                    raise ConnectorConnectionError(
                        f"Unable to connect to PostgreSQL: {exc}"
                    ) from exc
        return self._pool

    async def _fetch(self, sql: str) -> tuple[list[str], list[tuple]]:
        pool = await self._get_pool()
        try:
            async with pool.acquire() as connection:
                statement = await connection.prepare(sql)
                records = await statement.fetch()
                columns = [attr.name for attr in statement.get_attributes()]
                rows = [tuple(record) for record in records]
                return columns, rows
        except ConnectorError:
            raise
        except Exception as exc:  # noqa: BLE001 - normalised to connector error
            raise QueryExecutionError(f"PostgreSQL query failed: {exc}") from exc
