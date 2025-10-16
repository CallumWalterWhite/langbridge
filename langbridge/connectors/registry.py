"""
Connector registry responsible for instantiating SqlConnector implementations.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Protocol

from .base import ConnectorError, SqlConnector

LOGGER = logging.getLogger(__name__)


class VaultProtocol(Protocol):
    """
    Minimal protocol for secret retrieval.
    """

    async def get_secret(self, secret_ref: str) -> Dict[str, Any]:
        ...  # pragma: no cover


@dataclass(slots=True)
class DataSource:
    """
    Dataclass describing datasource configuration needed to build connectors.
    """

    id: str
    type: str
    config: Dict[str, Any]
    secret_ref: Optional[str]
    workspace_id: Optional[str] = None


ConnectorFactory = Callable[[DataSource, Dict[str, Any]], SqlConnector]


class ConnectorRegistry:
    """
    Registry mapping datasource provider names to connector factory functions.
    """

    def __init__(
        self,
        *,
        vault: VaultProtocol,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._vault = vault
        self._logger = logger or LOGGER
        self._providers: Dict[str, ConnectorFactory] = {}

    def register(self, provider_name: str, factory: ConnectorFactory) -> None:
        key = provider_name.lower()
        self._providers[key] = factory
        self._logger.debug("Registered connector provider '%s'", key)

    async def get_for_datasource(self, datasource: DataSource) -> SqlConnector:
        provider_key = datasource.type.lower()
        factory = self._providers.get(provider_key)
        if not factory:
            raise ConnectorError(f"No connector registered for provider '{datasource.type}'.")

        secrets: Dict[str, Any] = {}
        if datasource.secret_ref:
            try:
                secrets = await self._vault.get_secret(datasource.secret_ref)
            except Exception as exc:
                raise ConnectorError(f"Failed to resolve secrets for datasource '{datasource.id}': {exc}") from exc

        connector = factory(datasource, secrets)
        return connector


__all__ = ["ConnectorRegistry", "DataSource", "VaultProtocol", "ConnectorFactory"]
