from langbridge.connectors.base.config import (
    ConnectorCapabilities,
    ConnectorFamily,
    ConnectorRuntimeType,
)
from langbridge.plugins import ConnectorPlugin, register_connector_plugin

from .config import (
    SALESFORCE_AUTH_SCHEMA,
    SALESFORCE_SUPPORTED_RESOURCES,
    SALESFORCE_SYNC_STRATEGY,
    SalesforceConnectorConfigFactory,
    SalesforceConnectorConfigSchemaFactory,
)
from .connector import SalesforceApiConnector

PLUGIN = register_connector_plugin(
    ConnectorPlugin(
        connector_type=ConnectorRuntimeType.SALESFORCE,
        connector_family=ConnectorFamily.API,
        capabilities=ConnectorCapabilities(
            supports_synced_datasets=True,
            supports_incremental_sync=True,
        ),
        supported_resources=SALESFORCE_SUPPORTED_RESOURCES,
        auth_schema=SALESFORCE_AUTH_SCHEMA,
        sync_strategy=SALESFORCE_SYNC_STRATEGY,
        config_factory=SalesforceConnectorConfigFactory,
        config_schema_factory=SalesforceConnectorConfigSchemaFactory,
        api_connector_class=SalesforceApiConnector,
    )
)


def get_connector_plugin() -> ConnectorPlugin:
    return PLUGIN


def register_plugin() -> ConnectorPlugin:
    return PLUGIN
