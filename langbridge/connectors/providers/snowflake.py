"""
Snowflake connector implementation.
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
    import snowflake.connector  # type: ignore
    from snowflake.connector import errors as snowflake_errors  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    snowflake = None  # type: ignore
    snowflake_errors = None  # type: ignore
else:  # pragma: no cover - optional dependency
    snowflake = snowflake.connector  # type: ignore


class SnowflakeConnector(SqlConnector):
    """
    Snowflake SQL connector leveraging the official python driver.
    """

    def __init__(
        self,
        *,
        name: str,
        config: Dict[str, Any],
        credentials: Dict[str, Any],
        logger: Optional[logging.Logger] = None,
    ) -> None:
        super().__init__(name=name, dialect="snowflake", logger=logger)
        self._config = config
        self._credentials = credentials
        self._driver_available = snowflake is not None

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _ensure_driver(self) -> None:
        if not self._driver_available:
            raise ConnectorError(
                "snowflake-connector-python is required for Snowflake support."
            )

    def _connection_kwargs(self) -> Dict[str, Any]:
        cfg = {**self._config, **self._credentials}
        allowed = [
            "account",
            "user",
            "password",
            "database",
            "schema",
            "warehouse",
            "role",
            "region",
        ]
        return {key: cfg[key] for key in allowed if cfg.get(key) is not None}

    async def _with_connection(self, fn):
        self._ensure_driver()

        def run_callable():
            conn = snowflake.connect(**self._connection_kwargs())  # type: ignore[attr-defined]
            try:
                return fn(conn)
            finally:
                try:
                    conn.close()
                except Exception:
                    pass

        return await run_sync(run_callable)

    # ------------------------------------------------------------------ #
    # Overrides
    # ------------------------------------------------------------------ #

    async def _execute_select(
        self, sql: str, params: Dict[str, Any], *, timeout_s: Optional[int]
    ) -> Tuple[List[str], List[List[Any]]]:
        async def runner(connection):
            try:
                cursor = connection.cursor()
                try:
                    if timeout_s:
                        cursor.execute(
                            f"ALTER SESSION SET STATEMENT_TIMEOUT_IN_SECONDS = {int(timeout_s)}"
                        )
                    cursor.execute(sql, params)
                    rows = cursor.fetchall()
                    columns = [meta[0] for meta in cursor.description]
                    return columns, [list(row) for row in rows]
                finally:
                    cursor.close()
            except snowflake_errors.ProgrammingError as exc:  # type: ignore[attr-defined]
                message = str(exc)
                if "permission" in message.lower():
                    raise PermissionError(message) from exc
                raise QueryValidationError(message) from exc
            except snowflake_errors.DatabaseError as exc:  # type: ignore[attr-defined]
                message = str(exc)
                if "timeout" in message.lower():
                    raise TimeoutError(message) from exc
                if "authentication" in message.lower():
                    raise AuthError(message) from exc
                raise ConnectorError(message) from exc

        return await self._with_connection(runner)

    async def _fetch_schema(self, tables: Optional[Sequence[str]]) -> SchemaInfo:
        filter_clause = ""
        params: Dict[str, Any] = {}
        if tables:
            filter_clause = "AND table_name = ANY(%(tables)s)"
            params["tables"] = list(tables)

        sql = f"""
        SELECT table_name, column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = CURRENT_SCHEMA()
        {filter_clause}
        ORDER BY table_name, ordinal_position
        """

        columns, rows = await self._execute_select(sql, params, timeout_s=30)
        grouped: Dict[str, List[ColumnSchema]] = {}
        for table_name, column_name, data_type in rows:
            grouped.setdefault(table_name, []).append(ColumnSchema(name=column_name, type=str(data_type)))

        table_schemas = [
            TableSchema(name=table, columns=cols)
            for table, cols in grouped.items()
        ]
        return SchemaInfo(tables=table_schemas)
