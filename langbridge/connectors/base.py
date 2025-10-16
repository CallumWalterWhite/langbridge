"""
Connector interfaces and shared types for LangBridge SQL access.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Literal, Optional, Sequence, Tuple

Dialects = Literal["snowflake", "bigquery", "postgres", "mysql", "generic"]

LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ConnectorError(RuntimeError):
    """Base error for connector issues."""


class AuthError(ConnectorError):
    """Raised when authentication fails."""


class PermissionError(ConnectorError):
    """Raised when permissions are insufficient to run a query."""


class TimeoutError(ConnectorError):
    """Raised when a query times out."""


class QueryValidationError(ConnectorError):
    """Raised when an invalid or unsafe query is detected."""


# ---------------------------------------------------------------------------
# Result models
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class ColumnSchema:
    name: str
    type: str


@dataclass(slots=True)
class TableSchema:
    name: str
    columns: List[ColumnSchema] = field(default_factory=list)


@dataclass(slots=True)
class SchemaInfo:
    """
    Describes the available tables/columns in a datasource.
    """

    tables: List[TableSchema]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tables": [
                {"name": t.name, "columns": [vars(c) for c in t.columns]}
                for t in self.tables
            ]
        }


@dataclass(slots=True)
class QueryResult:
    """
    Normalised SQL execution result.
    """

    columns: List[str]
    rows: List[List[Any]]
    rowcount: int
    elapsed_ms: int
    sql: str

    def json_safe(self) -> Dict[str, Any]:
        """Return structure suitable for JSON serialization."""
        return {
            "columns": self.columns,
            "rows": [
                [
                    _json_safe(cell)
                    for cell in row
                ]
                for row in self.rows
            ],
            "rowcount": self.rowcount,
            "elapsed_ms": self.elapsed_ms,
            "sql": self.sql,
        }


def _json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()  # datetime/date/time
        except Exception:
            pass
    try:
        json.dumps(value)
        return value
    except TypeError:
        return str(value)


# ---------------------------------------------------------------------------
# SQL sanitisation helpers
# ---------------------------------------------------------------------------


SQL_COMMENT_RE = re.compile(r"--.*?$|/\*.*?\*/", re.MULTILINE | re.DOTALL)
SQL_LIMIT_RE = re.compile(r"\blimit\s+\d+", re.IGNORECASE)
SQL_COMMAND_RE = re.compile(r"^\s*(\w+)", re.IGNORECASE)

FORBIDDEN_KEYWORDS = (
    "insert",
    "update",
    "delete",
    "drop",
    "alter",
    "truncate",
    "merge",
    "create",
    "replace",
)


def ensure_select_statement(sql: str) -> None:
    """Raise QueryValidationError if the SQL statement is not a SELECT."""
    stripped = SQL_COMMENT_RE.sub("", sql).strip()
    if not stripped:
        raise QueryValidationError("Empty SQL statement.")
    match = SQL_COMMAND_RE.match(stripped)
    if not match:
        raise QueryValidationError("Unable to determine SQL command.")
    command = match.group(1).lower()
    if command != "select" and not stripped.lower().startswith("with "):
        raise QueryValidationError("Only SELECT queries are permitted.")
    lowered = stripped.lower()
    if any(keyword in lowered for keyword in FORBIDDEN_KEYWORDS):
        raise QueryValidationError("Query contains prohibited keywords for read-only access.")


def apply_limit(sql: str, max_rows: Optional[int]) -> str:
    if not max_rows or max_rows <= 0:
        return sql
    if SQL_LIMIT_RE.search(sql):
        return sql
    terminating_semicolon = ";" if sql.strip().endswith(";") else ""
    base = sql.strip().rstrip(";")
    return f"{base}\nLIMIT {max_rows}{terminating_semicolon}"


# ---------------------------------------------------------------------------
# Connector base
# ---------------------------------------------------------------------------


class SqlConnector(ABC):
    """
    Abstract async SQL connector used by LangBridge agents.
    """

    name: str
    dialect: Dialects

    def __init__(
        self,
        *,
        name: str,
        dialect: Dialects,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.name = name
        self.dialect = dialect
        self.logger = logger or logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    async def test_connection(self) -> Dict[str, Any]:
        start = time.perf_counter()
        try:
            await self.execute("SELECT 1", max_rows=1, timeout_s=10)
        except QueryValidationError:
            # Should not happen, but re-raise.
            raise
        except ConnectorError as exc:
            raise exc
        except Exception as exc:
            raise ConnectorError(f"Connection test failed: {exc}") from exc
        elapsed = int((time.perf_counter() - start) * 1000)
        return {"ok": True, "elapsed_ms": elapsed, "connector": self.name}

    async def execute(
        self,
        sql: str,
        params: Optional[Dict[str, Any]] = None,
        *,
        max_rows: Optional[int] = 5000,
        timeout_s: Optional[int] = 30,
    ) -> QueryResult:
        ensure_select_statement(sql)
        prepared_sql = apply_limit(sql, max_rows)
        self.logger.debug("Executing SQL (dialect=%s): %s", self.dialect, prepared_sql)

        start = time.perf_counter()
        try:
            columns, rows = await self._execute_select(
                prepared_sql,
                params or {},
                timeout_s=timeout_s,
            )
        except QueryValidationError:
            raise
        except AuthError:
            raise
        except PermissionError:
            raise
        except TimeoutError:
            raise
        except ConnectorError:
            raise
        except Exception as exc:
            raise ConnectorError(f"Execution failed: {exc}") from exc

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        rowcount = len(rows)
        self.logger.debug(
            "Execution completed (rows=%s elapsed_ms=%s)", rowcount, elapsed_ms
        )
        return QueryResult(columns=columns, rows=rows, rowcount=rowcount, elapsed_ms=elapsed_ms, sql=prepared_sql)

    async def get_schema(self, tables: Optional[Sequence[str]] = None) -> SchemaInfo:
        try:
            schema = await self._fetch_schema(tables)
        except Exception as exc:
            raise ConnectorError(f"Failed to fetch schema: {exc}") from exc
        return schema

    # ------------------------------------------------------------------ #
    # Abstract hooks for providers
    # ------------------------------------------------------------------ #

    @abstractmethod
    async def _execute_select(
        self, sql: str, params: Dict[str, Any], *, timeout_s: Optional[int]
    ) -> Tuple[List[str], List[List[Any]]]:
        """
        Execute a SELECT query and return columns/rows.
        Providers must override.
        """

    @abstractmethod
    async def _fetch_schema(self, tables: Optional[Sequence[str]]) -> SchemaInfo:
        """
        Retrieve schema metadata for the data source.
        """


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


async def run_sync(fn, *args, **kwargs):
    """
    Run blocking call in default thread pool.
    """

    return await asyncio.to_thread(fn, *args, **kwargs)

