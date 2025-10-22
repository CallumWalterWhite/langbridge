from enum import Enum
from .base import (
    SqlConnector,
    SchemaInfo,
    QueryResult,
    ConnectorError,
    AuthError,
    PermissionError,
    TimeoutError,
    QueryValidationError,
)

class ConnectorType(Enum):
    SQL = "SQL"
    NO_SQL = "NO_SQL"

class SqlDialetcs(Enum):
    POSTGRES = "POSTGRES"
    MYSQL = "MYSQL"
    MONGODB = "MONGODB"
    SNOWFLAKE = "SNOWFLAKE"
    REDSHIFT = "REDSHIFT"
    BIGQUERY = "BIGQUERY"
    SQLSERVER = "SQLSERVER"
    ORACLE = "ORACLE"
    SQLITE = "SQLITE"


__all__ = [
    'SqlConnector',
    'SchemaInfo',
    'QueryResult',
    'ConnectorError',
    'AuthError',
    'PermissionError',
    'TimeoutError',
    'QueryValidationError',
    'ConnectorType',
    'SqlDialetcs',
]

