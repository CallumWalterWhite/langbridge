from langbridge.packages.connectors.langbridge_connectors.api.config import (
    BaseConnectorConfig,
    BaseConnectorConfigFactory,
    BaseConnectorConfigSchemaFactory,
    ConnectorAuthFieldSchema,
    ConnectorConfigEntrySchema,
    ConnectorConfigSchema,
    ConnectorFamily,
    ConnectorPluginMetadata,
    ConnectorRuntimeType,
    ConnectorSyncStrategy,
)

SHOPIFY_SUPPORTED_RESOURCES = ("orders", "customers", "products")
SHOPIFY_AUTH_SCHEMA = (
    ConnectorAuthFieldSchema(
        field="shop_domain",
        label="Shop Domain",
        description="Shopify shop domain, for example `acme.myshopify.com`.",
        type="string",
        required=True,
    ),
    ConnectorAuthFieldSchema(
        field="access_token",
        label="Admin API Access Token",
        description="Private or custom app access token for the Admin API.",
        type="password",
        required=True,
        secret=True,
    ),
)
SHOPIFY_SYNC_STRATEGY = ConnectorSyncStrategy.INCREMENTAL


class ShopifyConnectorConfig(BaseConnectorConfig):
    shop_domain: str
    access_token: str
    api_version: str = "2025-01"


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
            name="Shopify",
            description="Connect to Shopify Admin API resources and ingest them as datasets.",
            version="0.1.0",
            label="Shopify",
            icon="shopify.png",
            connector_type="api",
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
                    label="Admin API Access Token",
                    description="Private or custom app access token for the Admin API.",
                    type="password",
                    required=True,
                ),
                ConnectorConfigEntrySchema(
                    field="api_version",
                    label="API Version",
                    description="Optional Shopify Admin API version.",
                    type="string",
                    required=False,
                    default="2025-01",
                ),
            ],
            plugin_metadata=ConnectorPluginMetadata(
                connector_type=ConnectorRuntimeType.SHOPIFY.value,
                connector_family=ConnectorFamily.API,
                supported_resources=list(SHOPIFY_SUPPORTED_RESOURCES),
                auth_schema=list(SHOPIFY_AUTH_SCHEMA),
                sync_strategy=SHOPIFY_SYNC_STRATEGY,
            ),
        )
