from __future__ import annotations

from langbridge.connectors import ConnectorConfig
from pydantic import Field


class ShopifyConnectorConfig(ConnectorConfig):
    """Connection configuration for the Shopify connector."""

    shop: str = Field(..., description="Shopify shop subdomain or full *.myshopify.com domain")
    access_token: str = Field(..., description="Shopify Admin API access token")
    api_version: str = Field("2024-07", description="Shopify Admin API version")
