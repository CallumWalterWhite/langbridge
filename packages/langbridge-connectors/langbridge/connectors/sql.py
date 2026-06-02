"""SQL connector base type.

`SqlConnector` is the base for database connectors that execute SQL directly.
Subclasses implement just three things — :meth:`_fetch`, :meth:`get_catalog`,
and :meth:`get_config_schema` — and inherit Arrow conversion, read-only query
validation, and resource streaming.
"""

from __future__ import annotations

import re
from abc import abstractmethod
from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Any, ClassVar

import pyarrow as pa

from .base import TConfig
from .errors import QueryValidationError, ResourceNotFoundError
from .models import (
    FieldType,
    LangbridgeCatalog,
    LangbridgeField,
    LangbridgeResource,
    LangbridgeSyncRequest,
)
from .source import SourceConnector

_SQL_COMMENT = re.compile(r"--[^\n]*|/\*.*?\*/", re.DOTALL)

_ARROW_CONVERSION_ERRORS: tuple[type[Exception], ...] = (
    pa.ArrowInvalid,
    pa.ArrowTypeError,
    pa.ArrowNotImplementedError,
    TypeError,
)


def ensure_select(sql: str) -> None:
    """Raise :class:`QueryValidationError` unless ``sql`` is a single read-only query.

    Langbridge is a read-only data access layer; only ``SELECT`` (and ``WITH``)
    statements are permitted through the public query surface.
    """
    stripped = _SQL_COMMENT.sub("", sql).strip().rstrip(";").strip()
    if not stripped:
        raise QueryValidationError("Empty SQL statement")
    if ";" in stripped:
        raise QueryValidationError("Multiple SQL statements are not permitted")
    lowered = stripped.lower()
    if not (lowered.startswith("select") or lowered.startswith("with")):
        raise QueryValidationError("Only read-only SELECT queries are permitted")


def quote_literal(value: str) -> str:
    """Quote a string as a SQL literal, escaping embedded single quotes."""
    return "'" + value.replace("'", "''") + "'"


def _array(values: list[Any], target: pa.DataType | None) -> pa.Array:
    """Build an Arrow array, falling back to stringification for exotic objects.

    Drivers occasionally return values Arrow cannot infer or cast directly
    (e.g. ``uuid.UUID``). When the destination type is textual we stringify;
    otherwise the original error is surfaced so genuine schema mismatches fail
    loudly.
    """
    try:
        array = pa.array(values)
        return array if target is None else array.cast(target)
    except _ARROW_CONVERSION_ERRORS:
        if target is not None and pa.types.is_string(target):
            return pa.array([None if v is None else str(v) for v in values], type=pa.string())
        raise


def _infer_table(columns: Sequence[str], rows: Sequence[tuple]) -> pa.Table:
    """Build an Arrow table with inferred column types (used for ad-hoc queries)."""
    if not columns:
        return pa.table({})
    arrays = [_array([row[idx] for row in rows], None) for idx in range(len(columns))]
    return pa.Table.from_arrays(arrays, names=list(columns))


def _typed_batch(rows: Sequence[tuple], schema: pa.Schema) -> pa.RecordBatch:
    """Build a record batch whose columns match a declared Arrow schema."""
    arrays = [
        _array([row[idx] for row in rows], schema.field(idx).type)
        for idx in range(len(schema))
    ]
    return pa.RecordBatch.from_arrays(arrays, schema=schema)


class SqlConnector(SourceConnector[TConfig]):
    """Base class for connectors that execute SQL against a database."""

    #: SQL dialect identifier, consumed by the federation planner for pushdown.
    dialect: ClassVar[str | None] = None
    #: Whether the planner may push query fragments down to this source.
    supports_pushdown: ClassVar[bool] = True

    @abstractmethod
    async def _fetch(self, sql: str) -> tuple[list[str], list[tuple]]:
        """Execute ``sql`` and return ``(column_names, rows)``.

        This is the single I/O primitive a SQL connector must implement.
        """
        raise NotImplementedError

    async def test_connection(self) -> None:
        await self._fetch("SELECT 1")

    async def execute(self, sql: str) -> pa.Table:
        """Execute a read-only SQL query and return an Arrow table.

        Column types are inferred from the result. For catalog-typed data use
        :meth:`fetch_resource` instead.
        """
        ensure_select(sql)
        columns, rows = await self._fetch(sql)
        return _infer_table(columns, rows)

    async def fetch_resource(
        self,
        request: LangbridgeSyncRequest,
    ) -> AsyncIterator[pa.RecordBatch]:
        catalog = await self.get_catalog()
        resource = catalog.get_resource(request.resource)
        if resource is None:
            raise ResourceNotFoundError(request.resource)

        schema = resource.to_arrow_schema()
        column_list = ", ".join(self._quote_identifier(f.name) for f in resource.fields)
        sql = f"SELECT {column_list} FROM {self._qualified_name(resource)}"
        if request.cursor_value is not None and resource.cursor_field:
            sql += (
                f" WHERE {self._quote_identifier(resource.cursor_field)}"
                f" > {quote_literal(request.cursor_value)}"
            )

        _, rows = await self._fetch(sql)
        if not rows:
            yield pa.RecordBatch.from_pylist([], schema=schema)
            return
        for start in range(0, len(rows), request.batch_size):
            yield _typed_batch(rows[start : start + request.batch_size], schema)

    def _quote_identifier(self, name: str) -> str:
        """Quote a table/column identifier. Override per dialect as needed."""
        return '"' + name.replace('"', '""') + '"'

    def _qualified_name(self, resource: LangbridgeResource) -> str:
        """Return the dialect-quoted, namespace-qualified name of a resource."""
        if resource.namespace:
            return (
                f"{self._quote_identifier(resource.namespace)}"
                f".{self._quote_identifier(resource.name)}"
            )
        return self._quote_identifier(resource.name)

    async def _information_schema_catalog(
        self,
        *,
        schema: str,
        type_map: Mapping[str, FieldType],
        catalog_name: str,
        catalog_description: str,
    ) -> LangbridgeCatalog:
        """Build a catalog by introspecting the standard ``information_schema``.

        Works for any database exposing the SQL-standard ``information_schema``
        (PostgreSQL, MySQL, ...). The schema name is inlined as a quoted literal
        because it originates from trusted deployment configuration, never from
        agent input — keeping :meth:`_fetch` free of dialect-specific binding.
        """
        schema_literal = quote_literal(schema)

        _, column_rows = await self._fetch(
            "SELECT table_name, column_name, data_type, is_nullable "
            "FROM information_schema.columns "
            f"WHERE table_schema = {schema_literal} "
            "ORDER BY table_name, ordinal_position"
        )
        _, pk_rows = await self._fetch(
            "SELECT kcu.table_name, kcu.column_name "
            "FROM information_schema.table_constraints tc "
            "JOIN information_schema.key_column_usage kcu "
            "  ON tc.constraint_name = kcu.constraint_name "
            " AND tc.table_schema = kcu.table_schema "
            " AND tc.table_name = kcu.table_name "
            "WHERE tc.constraint_type = 'PRIMARY KEY' "
            f"  AND tc.table_schema = {schema_literal}"
        )

        primary_keys: dict[str, list[str]] = {}
        for table_name, column_name in pk_rows:
            primary_keys.setdefault(table_name, []).append(column_name)

        fields_by_table: dict[str, list[LangbridgeField]] = {}
        for table_name, column_name, data_type, is_nullable in column_rows:
            fields_by_table.setdefault(table_name, []).append(
                LangbridgeField(
                    name=column_name,
                    description=f"{data_type} column",
                    type=type_map.get(str(data_type).lower(), FieldType.STRING),
                    required=str(is_nullable).strip().upper() == "NO",
                )
            )

        resources = [
            LangbridgeResource(
                name=table_name,
                description=f"'{table_name}' table in schema '{schema}'",
                namespace=schema,
                primary_key=primary_keys.get(table_name, []),
                cursor_field=None,
                fields=fields,
            )
            for table_name, fields in sorted(fields_by_table.items())
        ]
        return LangbridgeCatalog(
            name=catalog_name,
            description=catalog_description,
            resources=resources,
        )
