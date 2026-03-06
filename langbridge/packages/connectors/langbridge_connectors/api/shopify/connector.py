from __future__ import annotations

from typing import Any

from langbridge.packages.connectors.langbridge_connectors.api._http_api_connector import (
    ApiResourceDefinition,
    HttpApiConnector,
    flatten_api_records,
    parse_link_header_cursor,
)
from langbridge.packages.connectors.langbridge_connectors.api.config import (
    ConnectorRuntimeType,
)
from langbridge.packages.connectors.langbridge_connectors.api.connector import (
    ApiExtractResult,
    ApiResource,
)

from .config import SHOPIFY_SUPPORTED_RESOURCES, ShopifyConnectorConfig


class ShopifyApiConnector(HttpApiConnector):
    RUNTIME_TYPE = ConnectorRuntimeType.SHOPIFY
    SUPPORTED_RESOURCES = SHOPIFY_SUPPORTED_RESOURCES
    RESOURCE_DEFINITIONS = {
        "orders": ApiResourceDefinition(
            resource=ApiResource(
                name="orders",
                label="Orders",
                primary_key="id",
                cursor_field="page_info",
            ),
            path="/orders.json",
            response_key="orders",
        ),
        "customers": ApiResourceDefinition(
            resource=ApiResource(
                name="customers",
                label="Customers",
                primary_key="id",
                cursor_field="page_info",
            ),
            path="/customers.json",
            response_key="customers",
        ),
        "products": ApiResourceDefinition(
            resource=ApiResource(
                name="products",
                label="Products",
                primary_key="id",
                cursor_field="page_info",
            ),
            path="/products.json",
            response_key="products",
        ),
    }

    def __init__(self, config: ShopifyConnectorConfig, logger=None, **kwargs: Any) -> None:
        super().__init__(config=config, logger=logger, **kwargs)

    def _base_url(self) -> str:
        return f"https://{self.config.shop_domain.strip().rstrip('/')}/admin/api/{self.config.api_version.strip()}"

    def _default_headers(self) -> dict[str, str]:
        return {
            "X-Shopify-Access-Token": self.config.access_token,
        }

    async def test_connection(self) -> None:
        await self._request_json("GET", "/shop.json")

    async def extract_resource(
        self,
        resource_name: str,
        *,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> ApiExtractResult:
        definition = self._require_resource(resource_name)
        page_size = self._clamp_limit(limit, default=50, maximum=250)
        params: dict[str, Any] = {"limit": page_size}
        if cursor:
            params["page_info"] = cursor
        elif resource_name == "orders":
            params["status"] = "any"

        payload, response = await self._request_json(
            "GET",
            definition.path,
            params=params,
        )
        records = payload.get(definition.response_key or definition.resource.name, [])
        if not isinstance(records, list):
            records = []

        flattened_records, child_records = flatten_api_records(
            resource_name=definition.resource.name,
            records=[record for record in records if isinstance(record, dict)],
            primary_key=definition.resource.primary_key,
        )
        return ApiExtractResult(
            resource=definition.resource.name,
            status="success",
            records=flattened_records,
            next_cursor=parse_link_header_cursor(response.headers.get("Link")),
            child_records=child_records,
        )
