from __future__ import annotations

from pydantic import Field

from ...models import ConnectorConfig


class MySQLConnectorConfig(ConnectorConfig):
    """Connection configuration for the MySQL connector."""

    host: str = Field(..., description="Database host address")
    port: int = Field(3306, description="Database port")
    database: str = Field(..., description="Database name")
    user: str = Field(..., description="Database user")
    password: str = Field(..., description="Database password")
    pool_size: int = Field(5, ge=1, description="Maximum number of pooled connections")
