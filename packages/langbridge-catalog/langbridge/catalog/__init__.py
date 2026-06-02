"""langbridge-catalog — official connector implementations for Langbridge.

Connectors here are also advertised through the ``langbridge.connectors``
entry-point group, so an installed catalog is auto-discovered by
``ConnectorRegistry.load_entry_points()``. :func:`register_catalog` offers the
same wiring for development checkouts that are not pip-installed.
"""

from langbridge.connectors.registry import ConnectorRegistry
from langbridge.connectors.source import SourceConnector

from .shopify.connector import ShopifyConnector

CATALOG_CONNECTORS: tuple[type[SourceConnector], ...] = (ShopifyConnector,)


def register_catalog(registry: ConnectorRegistry) -> None:
    """Register every catalog connector into ``registry``."""
    for connector in CATALOG_CONNECTORS:
        registry.register(connector)


__all__ = ["CATALOG_CONNECTORS", "ShopifyConnector", "register_catalog"]
