"""
PostgreSQL connector leveraging psycopg (v3).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..base import (
    AuthError,
    ConnectorError,
    PermissionError,
    QueryValidationError,
    TimeoutError,
    SchemaInfo,
    SqlConnector,
    TableSchema,
    ColumnSchema,
    run_sync,
)

try:  # pragma: no cover - optional dependency
    import psycopg  # type: ignore
    from psycopg import sql as psycopg_sql  # type: ignore
    from psycopg.errors import OperationalError, ProgrammingError, QueryCanceled  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    psycopg = None  # type: ignore
    psycopg_sql = None  # type: ignore
    OperationalError = ProgrammingError = QueryCanceled = Exception  # type: ignore


class PostgresConnector(SqlConnector):
    """
    PostgreSQL connector built on psycopg 3.
    """

    def __init__(
        self,
        *,
        name: str,
        config: Dict[str, Any],
        credentials: Dict[str, Any],
        logger: Optional[logging.Logger] = None,
    ) -> None:
        super().__init__(name=name, dialect="postgres", logger=logger)
        self._config = config
        self._credentials = credentials
        self._driver_available = psycopg is not None

    def _ensure_driver(self) -> None:
        if not self._driver_available:
            raise ConnectorError("psycopg (v3) is required for PostgreSQL support.")

    def _connection_kwargs(self) -> Dict[str, Any]:
        cfg = {**self._config, **self._credentials}
        allowed = [
            "host",
            "port",
            "dbname",
            "database",
            "user",
            "password",
            "sslmode",
        ]
        kwargs = {key: cfg.get(key) for key in allowed if cfg.get(key) is not None}
        if "database" in kwargs and "dbname" not in kwargs:
            kwargs["dbname"] = kwargs.pop("database")
        return kwargs

    async def _with_connection(self, fn):
        self._ensure_driver()

        def run_callable():
            conn = psycopg.connect(**self._connection_kwargs())  # type: ignore[attr-defined]
            try:
                return fn(conn)
            finally:
                conn.close()

        return await run_sync(run_callable)

    async def _execute_select(
        self, sql: str, params: Dict[str, Any], *, timeout_s: Optional[int]
    ) -> Tuple[List[str], List[List[Any]]]:
        async def runner(connection):
            try:
                if timeout_s:
                    connection.execute(f"SET statement_timeout = {int(timeout_s * 1000)}")
                with connection.cursor() as cursor:
                    cursor.execute(sql, params or None)
                    rows = cursor.fetchall()
                    columns = [desc.name for desc in cursor.description]
                    return columns, [list(row) for row in rows]
            except QueryCanceled as exc:  # type: ignore[attr-defined]
                raise TimeoutError(str(exc)) from exc
            except OperationalError as exc:  # type: ignore[attr-defined]
                message = str(exc)
                if "authentication" in message.lower():
                    raise AuthError(message) from exc
                raise ConnectorError(message) from exc
            except ProgrammingError as exc:  # type: ignore[attr-defined]
                raise QueryValidationError(str(exc)) from exc

        return await self._with_connection(runner)

    async def _fetch_schema(self, tables: Optional[Sequence[str]]) -> SchemaInfo:
        async def runner(connection):
            filter_clause = ""
            params: Dict[str, Any] = {"schema": self._config.get("schema", "public")}
            if tables:
                filter_clause = "AND table_name = ANY(%(tables)s)"
                params["tables"] = list(tables)

            query = """
            SELECT table_name, column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = %(schema)s
            {filter_clause}
            ORDER BY table_name, ordinal_position
            """.format(filter_clause=filter_clause)

            with connection.cursor() as cursor:
                cursor.execute(query, params)
                rows = cursor.fetchall()

            grouped: Dict[str, List[ColumnSchema]] = {}
            for table_name, column_name, data_type in rows:
                grouped.setdefault(table_name, []).append(
                    ColumnSchema(name=column_name, type=data_type)
                )
            return [
                TableSchema(name=table, columns=cols) for table, cols in grouped.items()
            ]

        tables_schema = await self._with_connection(runner)
        return SchemaInfo(tables=tables_schema)

