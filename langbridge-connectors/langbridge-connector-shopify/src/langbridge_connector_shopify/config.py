from pydantic import model_validator

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
    "langbridge_connector_shopify.manifests",
    "shopify.yaml",
)


class ShopifyConnectorConfig(BaseConnectorConfig):
    shop_domain: str
    access_token: str | None = None
    shopify_app_client_id: str | None = None
    shopify_app_client_secret: str | None = None
    api_base_url: str | None = None

    @model_validator(mode="after")
    def _validate_auth(self) -> "ShopifyConnectorConfig":
        if str(self.access_token or "").strip():
            return self
        if str(self.shopify_app_client_id or "").strip() and str(
            self.shopify_app_client_secret or ""
        ).strip():
            return self
        raise ValueError(
            "Provide either access_token or both shopify_app_client_id and "
            "shopify_app_client_secret."
        )


class ShopifyConnectorConfigFactory(BaseConnectorConfigFactory):
    type = ConnectorRuntimeType.SHOPIFY

    @classmethod
    def create(cls, config: dict) -> BaseConnectorConfig:
        return ShopifyConnectorConfig(**config)


class ShopifyConnectorConfigSchemaFactory(BaseConnectorConfigSchemaFactory):
    type = ConnectorRuntimeType.SHOPIFY

    @classmethod
    def create(cls, _: dict) -> ConnectorConfigSchema:
        return ConnectorConfigSchema(
            name=_MANIFEST.display_name,
            description=(
                f"{_MANIFEST.description} The package supports either a direct Admin API "
                "access token or the legacy app client id/secret flow and derives the "
                "shop-specific Admin API base URL from `shop_domain` unless "
                "`api_base_url` is explicitly overridden."
            ),
            version=_MANIFEST.schema_version,
            config=[
                ConnectorConfigEntrySchema(
                    field="shop_domain",
                    label="Shop Domain",
                    description="Shopify shop domain, for example `acme.myshopify.com`.",
                    type="string",
                    required=True,
                ),
                ConnectorConfigEntrySchema(
                    field="access_token",
                    label="Access Token",
                    description="Preferred Shopify Admin API access token.",
                    type="password",
                    required=False,
                ),
                ConnectorConfigEntrySchema(
                    field="shopify_app_client_id",
                    label="Shopify App Client ID",
                    description="Legacy Shopify app client id used to obtain an access token.",
                    type="string",
                    required=False,
                ),
                ConnectorConfigEntrySchema(
                    field="shopify_app_client_secret",
                    label="Shopify App Client Secret",
                    description="Legacy Shopify app client secret used to obtain an access token.",
                    type="password",
                    required=False,
                ),
                ConnectorConfigEntrySchema(
                    field="api_base_url",
                    label="API Base URL",
                    description=(
                        "Optional Shopify Admin API base URL override. Defaults to "
                        "`https://{shop_domain}/admin/api/2025-01`."
                    ),
                    type="string",
                    required=False,
                ),
            ],
            plugin_metadata=build_declarative_plugin_metadata(
                _MANIFEST,
                connector_type=ConnectorRuntimeType.SHOPIFY,
                auth_schema=SHOPIFY_AUTH_SCHEMA,
                sync_strategy=ConnectorSyncStrategy.INCREMENTAL,
            ),
        )


SHOPIFY_MANIFEST = _MANIFEST
SHOPIFY_SUPPORTED_RESOURCES = _MANIFEST.resource_keys
SHOPIFY_SYNC_STRATEGY = ConnectorSyncStrategy.INCREMENTAL
SHOPIFY_AUTH_SCHEMA = (
    ConnectorAuthFieldSchema(
        field="shop_domain",
        label="Shop Domain",
        description="Shopify shop domain, for example `acme.myshopify.com`.",
        type="string",
        required=True,
        secret=False,
    ),
    ConnectorAuthFieldSchema(
        field="access_token",
        label="Access Token",
        description="Preferred Shopify Admin API access token.",
        type="password",
        required=False,
        secret=True,
    ),
    ConnectorAuthFieldSchema(
        field="shopify_app_client_id",
        label="Shopify App Client ID",
        description="Legacy Shopify app client id used to obtain an access token.",
        type="string",
        required=False,
        secret=False,
    ),
    ConnectorAuthFieldSchema(
        field="shopify_app_client_secret",
        label="Shopify App Client Secret",
        description="Legacy Shopify app client secret used to obtain an access token.",
        type="password",
        required=False,
        secret=True,
    ),
)

# Backward-compatible aliases while the package migrates away from the
# earlier declarative-only naming.
ShopifyDeclarativeConnectorConfig = ShopifyConnectorConfig
ShopifyDeclarativeConnectorConfigFactory = ShopifyConnectorConfigFactory
ShopifyDeclarativeConnectorConfigSchemaFactory = ShopifyConnectorConfigSchemaFactory
