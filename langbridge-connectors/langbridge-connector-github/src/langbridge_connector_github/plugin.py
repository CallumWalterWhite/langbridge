from __future__ import annotations

from langbridge.connectors.base.config import ConnectorFamily, ConnectorRuntimeType
from langbridge.plugins import ConnectorPlugin, register_connector_plugin

from .config import (
    GITHUB_AUTH_SCHEMA,
    GITHUB_SUPPORTED_RESOURCES,
    GITHUB_SYNC_STRATEGY,
    GitHubDeclarativeConnectorConfigFactory,
    GitHubDeclarativeConnectorConfigSchemaFactory,
)
from .connector import GitHubDeclarativeApiConnector

PLUGIN = register_connector_plugin(
    ConnectorPlugin(
        connector_type=ConnectorRuntimeType.GITHUB,
        connector_family=ConnectorFamily.API,
        supported_resources=GITHUB_SUPPORTED_RESOURCES,
        auth_schema=GITHUB_AUTH_SCHEMA,
        sync_strategy=GITHUB_SYNC_STRATEGY,
        config_factory=GitHubDeclarativeConnectorConfigFactory,
        config_schema_factory=GitHubDeclarativeConnectorConfigSchemaFactory,
        api_connector_class=GitHubDeclarativeApiConnector,
    )
)


def get_connector_plugin() -> ConnectorPlugin:
    return PLUGIN


def register_plugin() -> ConnectorPlugin:
    return PLUGIN
