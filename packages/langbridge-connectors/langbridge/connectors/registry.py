"""Connector registry — discovery surface for builtin and third-party connectors.

Builtin connectors are registered at package import time. Third-party
connectors are discovered from any installed distribution that advertises a
``langbridge.connectors`` entry-point group, so ``pip install`` is all that is
needed to extend the catalog.
"""

from __future__ import annotations

from collections.abc import Iterator
from importlib.metadata import entry_points

from .errors import ConnectorConfigError, ConnectorNotRegisteredError
from .source import SourceConnector

ENTRY_POINT_GROUP = "langbridge.connectors"


class ConnectorRegistry:
    """A keyed collection of connector classes."""

    def __init__(self) -> None:
        self._connectors: dict[str, type[SourceConnector]] = {}

    def register(self, connector: type[SourceConnector]) -> None:
        """Register a connector class under its ``key`` attribute."""
        key = getattr(connector, "key", "")
        if not key:
            raise ConnectorConfigError(
                f"Connector {connector.__name__} must define a non-empty 'key' class attribute"
            )
        self._connectors[key] = connector

    def get(self, key: str) -> type[SourceConnector]:
        """Return the connector class registered under ``key``."""
        try:
            return self._connectors[key]
        except KeyError:
            raise ConnectorNotRegisteredError(key, self.available()) from None

    def available(self) -> list[str]:
        """Return all registered connector keys, sorted."""
        return sorted(self._connectors)

    def load_entry_points(self, group: str = ENTRY_POINT_GROUP) -> list[str]:
        """Discover and register connectors advertised by installed packages.

        Returns the list of keys that were registered.
        """
        loaded: list[str] = []
        for entry_point in entry_points(group=group):
            connector = entry_point.load()
            self.register(connector)
            loaded.append(getattr(connector, "key", entry_point.name))
        return loaded

    def __contains__(self, key: object) -> bool:
        return key in self._connectors

    def __iter__(self) -> Iterator[str]:
        return iter(self.available())

    def __len__(self) -> int:
        return len(self._connectors)


#: Process-wide default registry. Builtin connectors are registered into this
#: instance when ``langbridge.connectors`` is imported.
registry = ConnectorRegistry()
