"""Data source abstractions for the LangBridge experimental query engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Protocol, Sequence, runtime_checkable

from .exceptions import QueryEngineError, QueryExecutionError


@dataclass(frozen=True)
class TableHandle:
    """Represents a table path within a data source."""

    path: Sequence[str]

    def __post_init__(self) -> None:
        if not self.path:
            raise ValueError("TableHandle path must contain at least one identifier")

    def sql_path(self) -> str:
        return ".".join(self.path)


@dataclass
class RawTable:
    """Raw table data as returned from a data source."""

    name: str
    columns: Sequence[str]
    rows: Sequence[Mapping[str, Any]]

    def materialize(self) -> tuple[List[str], List[Dict[str, Any]]]:
        cols = list(self.columns)
        return cols, [dict(row) for row in self.rows]


@runtime_checkable
class DataSource(Protocol):
    """Protocol that all queryable data sources must implement."""

    name: str

    def fetch_table(self, table: TableHandle, columns: Sequence[str] | None = None) -> RawTable:
        """
        Retrieve the requested table.

        Parameters
        ----------
        table:
            The table path within the data source (excluding the source name).
        columns:
            Optional projection of columns to return.
        """


class DataSourceRegistry:
    """Stores registered data sources by name."""

    def __init__(self):
        self._sources: Dict[str, DataSource] = {}

    def register(self, source: DataSource) -> None:
        key = source.name.lower()
        if key in self._sources:
            raise QueryEngineError(f"Data source {source.name!r} already registered")
        self._sources[key] = source

    def get(self, name: str) -> DataSource:
        key = name.lower()
        if key not in self._sources:
            raise QueryEngineError(f"Data source {name!r} is not registered")
        return self._sources[key]

    def has_source(self, name: str) -> bool:
        return name.lower() in self._sources


class SQLQueryRunnerDataSource(DataSource):
    """
    Helper base class for SQL-speaking sources.

    Subclasses must override :meth:`_run_query` to execute the provided SQL and
    return a :class:`RawTable`.
    """

    def __init__(self, name: str):
        self.name = name

    def fetch_table(self, table: TableHandle, columns: Sequence[str] | None = None) -> RawTable:
        column_sql = self._format_columns(columns)
        table_sql = self._format_table(table)
        sql = f"SELECT {column_sql} FROM {table_sql}"
        raw = self._run_query(sql)
        if not isinstance(raw, RawTable):
            raise QueryExecutionError(
                f"Data source {self.name!r} returned an unexpected result from _run_query"
            )
        return raw

    def _format_columns(self, columns: Sequence[str] | None) -> str:
        if not columns:
            return "*"
        return ", ".join(columns)

    def _format_table(self, table: TableHandle) -> str:
        return ".".join(table.path)

    def _run_query(self, sql: str) -> RawTable:
        raise NotImplementedError


class BigQueryDataSource(SQLQueryRunnerDataSource):
    """BigQuery implementation using the official Google Cloud client."""

    def __init__(
        self,
        name: str,
        client: Any = None,
        *,
        project: Optional[str] = None,
        job_config: Any = None,
    ):
        super().__init__(name=name)
        if client is None:
            try:
                from google.cloud import bigquery  # type: ignore
            except ImportError as exc:  # pragma: no cover - optional dependency
                raise QueryEngineError(
                    "google-cloud-bigquery is required to use BigQueryDataSource"
                ) from exc
            client = bigquery.Client(project=project)
        self._client = client
        self._job_config = job_config

    def _format_table(self, table: TableHandle) -> str:
        return f"`{'.'.join(table.path)}`"

    def _run_query(self, sql: str) -> RawTable:
        query_job = self._client.query(sql, job_config=self._job_config)
        result = query_job.result()
        columns = [field.name for field in result.schema]
        rows = [dict(row.items()) for row in result]
        return RawTable(name=sql, columns=columns, rows=rows)


class SnowflakeDataSource(SQLQueryRunnerDataSource):
    """Snowflake implementation using the official connector."""

    def __init__(
        self,
        name: str,
        connection: Any = None,
        **connect_kwargs: Any,
    ):
        super().__init__(name=name)
        if connection is None:
            try:
                import snowflake.connector  # type: ignore
            except ImportError as exc:  # pragma: no cover - optional dependency
                raise QueryEngineError(
                    "snowflake-connector-python is required to use SnowflakeDataSource"
                ) from exc
            connection = snowflake.connector.connect(**connect_kwargs)
        self._connection = connection

    def _format_table(self, table: TableHandle) -> str:
        return ".".join(f'"{part}"' for part in table.path)

    def _run_query(self, sql: str) -> RawTable:
        cursor = self._connection.cursor()
        try:
            cursor.execute(sql)
            description = cursor.description or []
            columns = [col[0] for col in description]
            data_rows = cursor.fetchall()
            rows = [dict(zip(columns, row)) for row in data_rows]
            return RawTable(name=sql, columns=columns, rows=rows)
        finally:
            cursor.close()


class InMemoryDataSource(DataSource):
    """
    Simple in-memory data source backed by Python dictionaries.

    Useful for unit testing and local experimentation.
    """

    def __init__(self, name: str, tables: Mapping[str, Sequence[Mapping[str, Any]]]):
        self.name = name
        self._tables: Dict[str, List[Dict[str, Any]]] = {
            key.lower(): [dict(row) for row in rows]
            for key, rows in tables.items()
        }

    def fetch_table(self, table: TableHandle, columns: Sequence[str] | None = None) -> RawTable:
        key = ".".join(table.path).lower()
        if key not in self._tables:
            raise QueryExecutionError(f"Table {key!r} not found in data source {self.name!r}")

        stored_rows = self._tables[key]
        if not stored_rows:
            selected_columns = list(columns) if columns else []
            return RawTable(name=key, columns=selected_columns, rows=[])

        available_columns = list(stored_rows[0].keys())
        if columns:
            missing = [col for col in columns if col not in available_columns]
            if missing:
                raise QueryExecutionError(
                    f"Columns {missing!r} not present in table {key!r} within source {self.name!r}"
                )
            selected_columns = list(columns)
        else:
            selected_columns = available_columns

        rows = [{col: row.get(col) for col in selected_columns} for row in stored_rows]
        return RawTable(name=key, columns=selected_columns, rows=rows)


__all__ = [
    "BigQueryDataSource",
    "DataSource",
    "DataSourceRegistry",
    "InMemoryDataSource",
    "RawTable",
    "SQLQueryRunnerDataSource",
    "SnowflakeDataSource",
    "TableHandle",
]
