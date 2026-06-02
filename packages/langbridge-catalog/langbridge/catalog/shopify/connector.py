"""Shopify connector — synced access to a store's Admin REST API.

The connector paginates Shopify's cursor-based ``Link`` header, normalises each
deeply-nested API record into the flat scalar schema declared in
:mod:`schemas`, and lets :class:`DeclarativeConnector` handle Arrow conversion.
Incremental syncs are driven by the ``updated_at`` cursor field.
"""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import AsyncIterator, Callable
from datetime import datetime
from typing import Any

import httpx
from langbridge.connectors import (
    ConnectorAuthError,
    ConnectorCapabilities,
    ConnectorConfigEntrySchema,
    ConnectorConfigSchema,
    ConnectorConnectionError,
    ConnectorPluginMetadata,
    ConnectorSyncStrategy,
    DeclarativeConnector,
    FieldType,
    LangbridgeCatalog,
    LangbridgeResource,
    QueryExecutionError,
    ResourceNotFoundError,
)

from .config import ShopifyConnectorConfig
from .schemas import SHOPIFY_CATALOG

_MAX_PAGE_SIZE = 250
_MAX_RETRIES = 5
_BACKOFF_BASE_SECONDS = 1.0
_DEFAULT_RETRY_AFTER = 2.0
_LINK_NEXT = re.compile(r'<([^>]+)>;\s*rel="next"')


def _next_link(link_header: str | None) -> str | None:
    """Extract the ``rel="next"`` URL from a Shopify ``Link`` response header."""
    if not link_header:
        return None
    match = _LINK_NEXT.search(link_header)
    return match.group(1) if match else None


def _coerce(value: Any, field_type: FieldType) -> Any:
    """Convert a raw Shopify value to a Python type matching its field type."""
    if value is None or value == "":
        return None
    if field_type is FieldType.INTEGER:
        return int(value)
    if field_type is FieldType.FLOAT:
        return float(value)
    if field_type is FieldType.BOOLEAN:
        return bool(value)
    if field_type in (FieldType.TIMESTAMP, FieldType.DATE):
        return datetime.fromisoformat(value) if isinstance(value, str) else value
    if field_type is FieldType.JSON:
        return json.dumps(value)
    return str(value)


def _flatten_order(record: dict[str, Any]) -> dict[str, Any]:
    customer = record.get("customer") or {}
    return {
        "id": record.get("id"),
        "name": record.get("name"),
        "email": record.get("email"),
        "created_at": record.get("created_at"),
        "updated_at": record.get("updated_at"),
        "processed_at": record.get("processed_at"),
        "financial_status": record.get("financial_status"),
        "fulfillment_status": record.get("fulfillment_status"),
        "currency": record.get("currency"),
        "total_price": record.get("total_price"),
        "subtotal_price": record.get("subtotal_price"),
        "total_tax": record.get("total_tax"),
        "total_discounts": record.get("total_discounts"),
        "customer_id": customer.get("id"),
        "line_items_count": len(record.get("line_items") or []),
        "tags": record.get("tags"),
        "cancelled_at": record.get("cancelled_at"),
    }


def _flatten_product(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": record.get("id"),
        "title": record.get("title"),
        "handle": record.get("handle"),
        "product_type": record.get("product_type"),
        "vendor": record.get("vendor"),
        "status": record.get("status"),
        "created_at": record.get("created_at"),
        "updated_at": record.get("updated_at"),
        "published_at": record.get("published_at"),
        "tags": record.get("tags"),
        "variants_count": len(record.get("variants") or []),
    }


def _flatten_customer(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": record.get("id"),
        "email": record.get("email"),
        "first_name": record.get("first_name"),
        "last_name": record.get("last_name"),
        "created_at": record.get("created_at"),
        "updated_at": record.get("updated_at"),
        "state": record.get("state"),
        "orders_count": record.get("orders_count"),
        "total_spent": record.get("total_spent"),
        "tags": record.get("tags"),
        "verified_email": record.get("verified_email"),
    }


_FLATTENERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "orders": _flatten_order,
    "products": _flatten_product,
    "customers": _flatten_customer,
}


class ShopifyConnector(DeclarativeConnector[ShopifyConnectorConfig]):
    """Connector for a Shopify store's orders, products and customers."""

    key = "shopify"

    def __init__(self, config: ShopifyConnectorConfig) -> None:
        super().__init__(config)
        self._client_instance: httpx.AsyncClient | None = None

    @classmethod
    def get_config_schema(cls) -> ConnectorConfigSchema:
        return ConnectorConfigSchema(
            name="Shopify",
            description="Sync orders, products and customers from a Shopify store.",
            version="1.0.0",
            config=[
                ConnectorConfigEntrySchema(
                    field="shop",
                    label="Shop",
                    required=True,
                    description="Shop subdomain or full *.myshopify.com domain.",
                    type="string",
                ),
                ConnectorConfigEntrySchema(
                    field="access_token",
                    label="Access token",
                    required=True,
                    description="Shopify Admin API access token.",
                    type="password",
                    secret=True,
                ),
                ConnectorConfigEntrySchema(
                    field="api_version",
                    label="API version",
                    required=False,
                    default="2024-07",
                    description="Shopify Admin API version.",
                    type="string",
                ),
            ],
            plugin_metadata=ConnectorPluginMetadata(
                default_sync_strategy=ConnectorSyncStrategy.INCREMENTAL,
                capabilities=ConnectorCapabilities(
                    supports_synced_datasets=True,
                    supports_incremental_sync=True,
                    supports_preview=True,
                    supports_federated_execution=True,
                ),
            ),
        )

    async def connect(self) -> None:
        self._client()

    async def disconnect(self) -> None:
        if self._client_instance is not None:
            await self._client_instance.aclose()
            self._client_instance = None

    async def get_catalog(self) -> LangbridgeCatalog:
        return SHOPIFY_CATALOG

    async def test_connection(self) -> None:
        # `_request` raises ConnectorAuthError on 401/403; a 200 confirms the token.
        await self._request("shop.json")

    async def fetch_batches(
        self,
        resource: LangbridgeResource,
        cursor_value: str | None,
        batch_size: int,
    ) -> AsyncIterator[list[dict[str, Any]]]:
        flatten = _FLATTENERS.get(resource.name)
        if flatten is None:
            raise ResourceNotFoundError(resource.name)

        page_size = max(1, min(batch_size, _MAX_PAGE_SIZE))
        url: str | None = f"{resource.name}.json"
        params: dict[str, Any] | None = {"limit": page_size}
        if cursor_value:
            params["updated_at_min"] = cursor_value
        if resource.name == "orders":
            params["status"] = "any"

        while url is not None:
            response = await self._request(url, params)
            records = response.json().get(resource.name, [])
            if records:
                yield [
                    {f.name: _coerce(raw.get(f.name), f.type) for f in resource.fields}
                    for raw in (flatten(record) for record in records)
                ]
            # After the first page, Shopify requires following the opaque
            # page_info URL verbatim — no other query params are permitted.
            url = _next_link(response.headers.get("Link"))
            params = None

    def _base_url(self) -> str:
        shop = self.config.shop.strip()
        for prefix in ("https://", "http://"):
            shop = shop.removeprefix(prefix)
        shop = shop.rstrip("/").removesuffix(".myshopify.com")
        return f"https://{shop}.myshopify.com/admin/api/{self.config.api_version}/"

    def _client(self) -> httpx.AsyncClient:
        if self._client_instance is None:
            self._client_instance = httpx.AsyncClient(
                base_url=self._base_url(),
                headers={
                    "X-Shopify-Access-Token": self.config.access_token,
                    "Accept": "application/json",
                },
                timeout=httpx.Timeout(30.0),
            )
        return self._client_instance

    async def _request(
        self,
        url: str,
        params: dict[str, Any] | None = None,
    ) -> httpx.Response:
        """Issue a GET request, retrying on rate limits and transient errors."""
        client = self._client()
        last_error: Exception | None = None

        for attempt in range(_MAX_RETRIES):
            try:
                response = await client.get(url, params=params)
            except httpx.HTTPError as exc:
                last_error = exc
                await asyncio.sleep(_BACKOFF_BASE_SECONDS * (2**attempt))
                continue

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else _DEFAULT_RETRY_AFTER
                await asyncio.sleep(delay)
                continue
            if response.status_code in (401, 403):
                raise ConnectorAuthError(
                    f"Shopify rejected the access token (HTTP {response.status_code})"
                )
            if response.status_code >= 500:
                last_error = QueryExecutionError(
                    f"Shopify server error (HTTP {response.status_code})"
                )
                await asyncio.sleep(_BACKOFF_BASE_SECONDS * (2**attempt))
                continue
            if response.status_code >= 400:
                raise QueryExecutionError(
                    f"Shopify API error (HTTP {response.status_code}): {response.text[:200]}"
                )
            return response

        raise ConnectorConnectionError(
            f"Shopify request to '{url}' failed after {_MAX_RETRIES} attempts: {last_error}"
        )
