"""Builtin connectors bundled with langbridge-connectors.

These ship in-package so a default install always has database and file
access. Their drivers are optional extras (``asyncpg``, ``aiomysql``) imported
lazily — importing this package never requires a driver to be installed.
"""

from ..registry import ConnectorRegistry
from ..source import SourceConnector
from .files.connector import FileConnector
from .mysql.connector import MySQLConnector
from .postgres.connector import PostgresConnector
from .sqlite.connector import SqliteConnector

BUILTIN_CONNECTORS: tuple[type[SourceConnector], ...] = (
    FileConnector,
    MySQLConnector,
    PostgresConnector,
    SqliteConnector,
)


def register_builtins(registry: ConnectorRegistry) -> None:
    """Register every builtin connector into ``registry``."""
    for connector in BUILTIN_CONNECTORS:
        registry.register(connector)


__all__ = ["BUILTIN_CONNECTORS", "register_builtins"]
