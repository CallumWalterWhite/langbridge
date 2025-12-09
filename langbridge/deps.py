"""
Dependency helpers for orchestrator services.
"""


import logging
from functools import lru_cache
from typing import Dict

from .connectors.base import SqlConnector
from .connectors.registry import ConnectorRegistry, DataSource, VaultProtocol
from .connectors.providers.bigquery import BigQueryConnector
from .connectors.providers.mysql import MySqlConnector
from .connectors.providers.postgres import PostgresConnector
from .connectors.providers.snowflake import SnowflakeConnector

LOGGER = logging.getLogger(__name__)


class InMemoryVault(VaultProtocol):
    """
    Minimal vault implementation for tests/local development.
    """

    def __init__(self, secrets: Dict[str, dict]) -> None:
        self._secrets = secrets

    async def get_secret(self, secret_ref: str) -> dict:
        if secret_ref not in self._secrets:
            raise KeyError(f"Secret '{secret_ref}' not found.")
        return self._secrets[secret_ref]


@lru_cache(maxsize=1)
def provide_connector_registry(vault: VaultProtocol) -> ConnectorRegistry:
    """
    Construct and cache a ConnectorRegistry wired with built-in providers.
    """

    registry = ConnectorRegistry(vault=vault, logger=LOGGER)
    registry.register(
        "snowflake",
        lambda ds, secrets: SnowflakeConnector(
            name=f"snowflake:{ds.id}",
            config=ds.config,
            credentials=secrets,
            logger=LOGGER,
        ),
    )
    registry.register(
        "bigquery",
        lambda ds, secrets: BigQueryConnector(
            name=f"bigquery:{ds.id}",
            config=ds.config,
            credentials=secrets,
            logger=LOGGER,
        ),
    )
    registry.register(
        "postgres",
        lambda ds, secrets: PostgresConnector(
            name=f"postgres:{ds.id}",
            config=ds.config,
            credentials=secrets,
            logger=LOGGER,
        ),
    )
    registry.register(
        "mysql",
        lambda ds, secrets: MySqlConnector(
            name=f"mysql:{ds.id}",
            config=ds.config,
            credentials=secrets,
            logger=LOGGER,
        ),
    )
    return registry


async def get_connector(
    *,
    datasource: DataSource,
    registry: ConnectorRegistry,
) -> SqlConnector:
    """
    Resolve a SqlConnector for the given datasource using the registry.
    """

    return await registry.get_for_datasource(datasource)


__all__ = ["provide_connector_registry", "get_connector", "InMemoryVault"]
