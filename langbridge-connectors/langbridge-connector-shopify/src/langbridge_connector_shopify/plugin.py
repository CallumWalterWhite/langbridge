from __future__ import annotations

from langbridge.connectors.base.config import ConnectorFamily, ConnectorRuntimeType
from langbridge.plugins import ConnectorPlugin, register_connector_plugin

from .config import (
    SHOPIFY_AUTH_SCHEMA,
    SHOPIFY_SUPPORTED_RESOURCES,
    SHOPIFY_SYNC_STRATEGY,
    ShopifyDeclarativeConnectorConfigFactory,
    ShopifyDeclarativeConnectorConfigSchemaFactory,
)
from .connector import ShopifyDeclarativeApiConnector

PLUGIN = register_connector_plugin(
    ConnectorPlugin(
        connector_type=ConnectorRuntimeType.SHOPIFY,
        connector_family=ConnectorFamily.API,
        supported_resources=SHOPIFY_SUPPORTED_RESOURCES,
        auth_schema=SHOPIFY_AUTH_SCHEMA,
        sync_strategy=SHOPIFY_SYNC_STRATEGY,
        config_factory=ShopifyDeclarativeConnectorConfigFactory,
        config_schema_factory=ShopifyDeclarativeConnectorConfigSchemaFactory,
        api_connector_class=ShopifyDeclarativeApiConnector,
    )
)


def get_connector_plugin() -> ConnectorPlugin:
    return PLUGIN


def register_plugin() -> ConnectorPlugin:
    return PLUGIN
