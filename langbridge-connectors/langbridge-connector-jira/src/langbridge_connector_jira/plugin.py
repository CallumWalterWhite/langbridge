from __future__ import annotations

from langbridge.connectors.base.config import ConnectorFamily, ConnectorRuntimeType
from langbridge.plugins import ConnectorPlugin, register_connector_plugin

from .config import (
    JIRA_AUTH_SCHEMA,
    JIRA_SUPPORTED_RESOURCES,
    JIRA_SYNC_STRATEGY,
    JiraDeclarativeConnectorConfigFactory,
    JiraDeclarativeConnectorConfigSchemaFactory,
)
from .connector import JiraDeclarativeApiConnector

PLUGIN = register_connector_plugin(
    ConnectorPlugin(
        connector_type=ConnectorRuntimeType.JIRA,
        connector_family=ConnectorFamily.API,
        supported_resources=JIRA_SUPPORTED_RESOURCES,
        auth_schema=JIRA_AUTH_SCHEMA,
        sync_strategy=JIRA_SYNC_STRATEGY,
        config_factory=JiraDeclarativeConnectorConfigFactory,
        config_schema_factory=JiraDeclarativeConnectorConfigSchemaFactory,
        api_connector_class=JiraDeclarativeApiConnector,
    )
)


def get_connector_plugin() -> ConnectorPlugin:
    return PLUGIN


def register_plugin() -> ConnectorPlugin:
    return PLUGIN
