from __future__ import annotations

from pydantic import Field

from ...models import ConnectorConfig


class PostgresConnectorConfig(ConnectorConfig):
    """Connection configuration for the PostgreSQL connector."""

    host: str = Field(..., description="Database host address")
    port: int = Field(5432, description="Database port")
    database: str = Field(..., description="Database name")
    user: str = Field(..., description="Database user")
    password: str = Field(..., description="Database password")
    schema_: str = Field("public", alias="schema", description="Schema to introspect for the catalog")
    ssl: str | None = Field(None, description="Optional SSL mode (disable, require, verify-full, ...)")
    pool_size: int = Field(5, ge=1, description="Maximum number of pooled connections")
