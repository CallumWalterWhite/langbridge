"""SQLite connector — local-file SQL access via the standard library.

SQLite uses dynamic type affinity rather than rigid column types, so declared
date/time columns are surfaced as :attr:`FieldType.STRING`; their stored
representation (text or integer) is preserved without lossy coercion.
"""

from __future__ import annotations

import asyncio
import sqlite3

from ...errors import ConnectorError, QueryExecutionError
from ...models import (
    ConnectorCapabilities,
    ConnectorConfigEntrySchema,
    ConnectorConfigSchema,
    ConnectorPluginMetadata,
    ConnectorSyncStrategy,
    FieldType,
    LangbridgeCatalog,
    LangbridgeField,
    LangbridgeResource,
)
from ...sql import SqlConnector
from .config import SqliteConnectorConfig


def _field_type(declared: str | None) -> FieldType:
    """Map a SQLite declared column type to a logical field type."""
    text = (declared or "").upper()
    if "INT" in text:
        return FieldType.INTEGER
    if any(token in text for token in ("REAL", "FLOA", "DOUB", "DEC", "NUM")):
        return FieldType.FLOAT
    if "BLOB" in text:
        return FieldType.BINARY
    if "BOOL" in text:
        return FieldType.BOOLEAN
    return FieldType.STRING


class SqliteConnector(SqlConnector[SqliteConnectorConfig]):
    """Connector for SQLite database files."""

    key = "sqlite"
    dialect = "sqlite"

    @classmethod
    def get_config_schema(cls) -> ConnectorConfigSchema:
        return ConnectorConfigSchema(
            name="SQLite",
            description="Query a local SQLite database file via SQL.",
            version="1.0.0",
            config=[
                ConnectorConfigEntrySchema(
                    field="path",
                    label="Database path",
                    required=True,
                    description="Filesystem path to the SQLite database file.",
                    type="string",
                ),
            ],
            plugin_metadata=ConnectorPluginMetadata(
                default_sync_strategy=ConnectorSyncStrategy.FULL_REFRESH,
                capabilities=ConnectorCapabilities(
                    supports_live_datasets=True,
                    supports_synced_datasets=True,
                    supports_query_pushdown=True,
                    supports_preview=True,
                    supports_federated_execution=True,
                ),
            ),
        )

    async def get_catalog(self) -> LangbridgeCatalog:
        _, table_rows = await self._fetch(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' "
            "ORDER BY name"
        )

        resources: list[LangbridgeResource] = []
        for (table_name,) in table_rows:
            _, column_rows = await self._fetch(
                f"PRAGMA table_info({self._quote_identifier(table_name)})"
            )
            fields: list[LangbridgeField] = []
            primary_key: list[str] = []
            for _cid, name, declared_type, not_null, _default, pk_index in column_rows:
                fields.append(
                    LangbridgeField(
                        name=name,
                        description=f"{declared_type or 'dynamic'} column",
                        type=_field_type(declared_type),
                        required=bool(not_null),
                    )
                )
                if pk_index:
                    primary_key.append(name)
            resources.append(
                LangbridgeResource(
                    name=table_name,
                    description=f"'{table_name}' table",
                    namespace="main",
                    primary_key=primary_key,
                    cursor_field=None,
                    fields=fields,
                )
            )
        return LangbridgeCatalog(
            name="sqlite",
            description=f"SQLite database at '{self.config.path}'",
            resources=resources,
        )

    async def _fetch(self, sql: str) -> tuple[list[str], list[tuple]]:
        return await asyncio.to_thread(self._fetch_blocking, sql)

    def _fetch_blocking(self, sql: str) -> tuple[list[str], list[tuple]]:
        try:
            connection = sqlite3.connect(self.config.path)
        except sqlite3.Error as exc:
            raise ConnectorError(f"Unable to open SQLite database: {exc}") from exc
        try:
            cursor = connection.execute(sql)
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            rows = [tuple(row) for row in cursor.fetchall()]
            return columns, rows
        except sqlite3.Error as exc:
            raise QueryExecutionError(f"SQLite query failed: {exc}") from exc
        finally:
            connection.close()
