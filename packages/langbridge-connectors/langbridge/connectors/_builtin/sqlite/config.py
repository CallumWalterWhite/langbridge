from __future__ import annotations

from pydantic import Field

from ...models import ConnectorConfig


class SqliteConnectorConfig(ConnectorConfig):
    """Connection configuration for the SQLite connector."""

    path: str = Field(..., description="Filesystem path to the SQLite database file")
