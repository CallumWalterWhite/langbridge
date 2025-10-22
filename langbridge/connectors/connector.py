from abc import ABC, abstractmethod
from ast import Tuple
from dataclasses import dataclass
import logging
import time
from typing import Any, Dict, List, Optional
import json
import re

from connectors.base import QueryValidationError
from errors.connector_errors import AuthError, ConnectorError
from connectors.config import BaseConnectorConfig
from connectors.metadata import ColumnMetadata
from connectors import SqlDialetcs, ConnectorType

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


class Connector(ABC):
    """
    Base class for all connectors.
    """

    pass

class SqlConnector(Connector):
    """
    Base class for SQL connectors.
    """
    
    CONNECTOR_TYPE: ConnectorType = ConnectorType.SQL
    DIALECT: SqlDialetcs
    
    def __init__(
        self,
        config: BaseConnectorConfig,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.config = config
        self.logger = logger or logging.getLogger(__name__
    )

    @abstractmethod
    def test_connection(self) -> None:
        """
        Test the database connection.
        Raises ConnectorError if the connection fails.
        """
        raise NotImplementedError

    @abstractmethod
    def fetch_schemas(self) -> List[str]:
        raise NotImplementedError

    @abstractmethod
    def fetch_tables(self) -> List[str]:
        raise NotImplementedError
    
    @abstractmethod
    def fetch_columns(self) -> List[ColumnMetadata]:
        raise NotImplementedError

    
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
        
        self.logger.debug(
            "Executing SQL (max_rows=%s timeout_s=%s): %s",
            max_rows,
            timeout_s,
            prepared_sql,
        )
        
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

    @abstractmethod
    async def _execute_select(
        self,
        sql: str,
        params: Dict[str, Any],
        *,
        timeout_s: Optional[int] = 30,
    ) -> Tuple[List[str], List[List[Any]]]:
        """
        Execute a SELECT query and return the results.
        Must be implemented by subclasses.
        """
        raise NotImplementedError