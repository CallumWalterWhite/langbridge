from __future__ import annotations

from langbridge.connectors.base.config import ConnectorFamily, ConnectorRuntimeType
from langbridge.plugins import ConnectorPlugin, register_connector_plugin

from .config import (
    ASANA_AUTH_SCHEMA,
    ASANA_SUPPORTED_RESOURCES,
    ASANA_SYNC_STRATEGY,
    AsanaDeclarativeConnectorConfigFactory,
    AsanaDeclarativeConnectorConfigSchemaFactory,
)
from .connector import AsanaDeclarativeApiConnector

PLUGIN = register_connector_plugin(
    ConnectorPlugin(
        connector_type=ConnectorRuntimeType.ASANA,
        connector_family=ConnectorFamily.API,
        supported_resources=ASANA_SUPPORTED_RESOURCES,
        auth_schema=ASANA_AUTH_SCHEMA,
        sync_strategy=ASANA_SYNC_STRATEGY,
        config_factory=AsanaDeclarativeConnectorConfigFactory,
        config_schema_factory=AsanaDeclarativeConnectorConfigSchemaFactory,
        api_connector_class=AsanaDeclarativeApiConnector,
    )
)


def get_connector_plugin() -> ConnectorPlugin:
    return PLUGIN


def register_plugin() -> ConnectorPlugin:
    return PLUGIN
