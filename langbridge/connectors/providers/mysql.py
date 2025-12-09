"""
MySQL connector implementation using mysql-connector-python or PyMySQL.
"""


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
    import mysql.connector  # type: ignore
    from mysql.connector import errors as mysql_errors  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    mysql = None  # type: ignore
    mysql_errors = None  # type: ignore

try:  # pragma: no cover - optional dependency
    import pymysql  # type: ignore
    import pymysql.err as pymysql_errors  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    pymysql = None  # type: ignore
    pymysql_errors = None  # type: ignore


class MySqlConnector(SqlConnector):
    """
    MySQL connector supporting mysql-connector-python or PyMySQL.
    """

    def __init__(
        self,
        *,
        name: str,
        config: Dict[str, Any],
        credentials: Dict[str, Any],
        logger: Optional[logging.Logger] = None,
    ) -> None:
        super().__init__(name=name, dialect="mysql", logger=logger)
        self._config = config
        self._credentials = credentials
        self._driver = self._select_driver()

    def _select_driver(self):
        if mysql is not None:
            return ("mysql_connector", mysql, mysql_errors)
        if pymysql is not None:
            return ("pymysql", pymysql, pymysql_errors)
        raise ConnectorError(
            "Install either mysql-connector-python or PyMySQL to enable MySQL support."
        )

    def _connection_kwargs(self) -> Dict[str, Any]:
        cfg = {**self._config, **self._credentials}
        allowed = [
            "host",
            "port",
            "user",
            "password",
            "database",
            "ssl_ca",
        ]
        return {key: cfg.get(key) for key in allowed if cfg.get(key) is not None}

    async def _with_connection(self, fn):
        driver_name, driver, _ = self._driver

        def run_callable():
            if driver_name == "mysql_connector":
                connection = driver.connect(**self._connection_kwargs())
            else:
                connection = driver.connect(**self._connection_kwargs())
            try:
                return fn(connection)
            finally:
                try:
                    connection.close()
                except Exception:
                    pass

        return await run_sync(run_callable)

    async def _execute_select(
        self, sql: str, params: Dict[str, Any], *, timeout_s: Optional[int]
    ) -> Tuple[List[str], List[List[Any]]]:
        driver_name, driver, errors_module = self._driver

        async def runner(connection):
            try:
                cursor = connection.cursor()
                try:
                    if timeout_s:
                        if driver_name == "mysql_connector":
                            connection.cmd_query(
                                f"SET SESSION MAX_EXECUTION_TIME={int(timeout_s * 1000)}"
                            )
                        else:
                            cursor.execute(
                                f"SET SESSION MAX_EXECUTION_TIME={int(timeout_s * 1000)}"
                            )
                    cursor.execute(sql, params or None)
                    columns = [desc[0] for desc in cursor.description]
                    rows = cursor.fetchall()
                    return columns, [list(row) for row in rows]
                finally:
                    cursor.close()
            except Exception as exc:
                if errors_module is None:
                    raise ConnectorError(str(exc)) from exc
                if isinstance(exc, getattr(errors_module, "ProgrammingError", tuple())):
                    raise QueryValidationError(str(exc)) from exc
                if isinstance(exc, getattr(errors_module, "InterfaceError", tuple())):
                    raise ConnectorError(str(exc)) from exc
                if isinstance(exc, getattr(errors_module, "OperationalError", tuple())):
                    message = str(exc)
                    if "access denied" in message.lower():
                        raise AuthError(message) from exc
                    if "timeout" in message.lower():
                        raise TimeoutError(message) from exc
                    raise ConnectorError(message) from exc
                message = str(exc)
                if "permission" in message.lower():
                    raise PermissionError(message) from exc
                raise ConnectorError(message) from exc

        return await self._with_connection(runner)

    async def _fetch_schema(self, tables: Optional[Sequence[str]]) -> SchemaInfo:
        database = self._config.get("database")
        if not database:
            raise ConnectorError("MySQL configuration requires a database/schema name.")

        filter_clause = ""
        args: List[Any] = [database]
        if tables:
            placeholders = ", ".join(["%s"] * len(tables))
            filter_clause = f"AND table_name IN ({placeholders})"
            args.extend(list(tables))

        sql = f"""
        SELECT table_name, column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = %s
        {filter_clause}
        ORDER BY table_name, ordinal_position
        """

        async def runner(connection):
            cursor = connection.cursor()
            try:
                cursor.execute(sql, args)
                rows = cursor.fetchall()
            finally:
                cursor.close()

            grouped: Dict[str, List[ColumnSchema]] = {}
            for table_name, column_name, data_type in rows:
                grouped.setdefault(table_name, []).append(
                    ColumnSchema(name=column_name, type=data_type)
                )
            return [
                TableSchema(name=table, columns=cols) for table, cols in grouped.items()
            ]

        table_schemas = await self._with_connection(runner)
        return SchemaInfo(tables=table_schemas)
