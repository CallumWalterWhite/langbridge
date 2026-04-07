from pydantic import AliasChoices, Field

from langbridge.connectors.base.config import (
    BaseConnectorConfig,
    BaseConnectorConfigFactory,
    BaseConnectorConfigSchemaFactory,
    ConnectorAuthFieldSchema,
    ConnectorConfigEntrySchema,
    ConnectorConfigSchema,
    ConnectorRuntimeType,
    ConnectorSyncStrategy,
)
from langbridge.connectors.saas.declarative import (
    build_declarative_plugin_metadata,
    load_declarative_connector_manifest,
)

_MANIFEST = load_declarative_connector_manifest(
    "langbridge_connector_hubspot.manifests",
    "hubspot.yaml",
)


class HubSpotConnectorConfig(BaseConnectorConfig):
    access_token: str = Field(validation_alias=AliasChoices("access_token", "service_key"))
    portal_id: str | None = None
    api_base_url: str = "https://api.hubapi.com"

    @property
    def service_key(self) -> str:
        return self.access_token


class HubSpotConnectorConfigFactory(BaseConnectorConfigFactory):
    type = ConnectorRuntimeType.HUBSPOT

    @classmethod
    def create(cls, config: dict) -> BaseConnectorConfig:
        return HubSpotConnectorConfig(**config)


class HubSpotConnectorConfigSchemaFactory(BaseConnectorConfigSchemaFactory):
    type = ConnectorRuntimeType.HUBSPOT

    @classmethod
    def create(cls, _: dict) -> ConnectorConfigSchema:
        return ConnectorConfigSchema(
            name=_MANIFEST.display_name,
            description=(
                f"{_MANIFEST.description} Manifest-defined HubSpot CRM resources execute "
                "through the core declarative HTTP SaaS runtime. The package accepts both "
                "the canonical `access_token` field and the legacy `service_key` alias."
            ),
            version=_MANIFEST.schema_version,
            config=[
                ConnectorConfigEntrySchema(
                    field="access_token",
                    label="Private App Token",
                    description="HubSpot private app access token. Legacy `service_key` is also accepted.",
                    type="password",
                    required=True,
                ),
                ConnectorConfigEntrySchema(
                    field="portal_id",
                    label="Portal ID",
                    description="Optional HubSpot portal identifier retained for compatibility.",
                    type="string",
                    required=False,
                ),
                ConnectorConfigEntrySchema(
                    field="api_base_url",
                    label="API Base URL",
                    description="Optional HubSpot API base URL override.",
                    type="string",
                    required=False,
                    default="https://api.hubapi.com",
                ),
            ],
            plugin_metadata=build_declarative_plugin_metadata(
                _MANIFEST,
                connector_type=ConnectorRuntimeType.HUBSPOT,
                auth_schema=HUBSPOT_AUTH_SCHEMA,
                sync_strategy=ConnectorSyncStrategy.INCREMENTAL,
            ),
        )


HUBSPOT_MANIFEST = _MANIFEST
HUBSPOT_SUPPORTED_RESOURCES = _MANIFEST.resource_keys
HUBSPOT_SYNC_STRATEGY = ConnectorSyncStrategy.INCREMENTAL
HUBSPOT_AUTH_SCHEMA = (
    ConnectorAuthFieldSchema(
        field="access_token",
        label="Private App Token",
        description="HubSpot private app access token. Legacy `service_key` is also accepted.",
        type="password",
        required=True,
        secret=True,
    ),
    ConnectorAuthFieldSchema(
        field="portal_id",
        label="Portal ID",
        description="Optional HubSpot portal identifier retained for compatibility.",
        type="string",
        required=False,
        secret=False,
    ),
)

HubSpotDeclarativeConnectorConfig = HubSpotConnectorConfig
HubSpotDeclarativeConnectorConfigFactory = HubSpotConnectorConfigFactory
HubSpotDeclarativeConnectorConfigSchemaFactory = HubSpotConnectorConfigSchemaFactory
