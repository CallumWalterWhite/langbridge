"""Static catalog definition for the Shopify connector.

Shopify's Admin API resources have well-known shapes, so the catalog is
declared up front rather than introspected. Each resource is flattened to a
scalar schema — nested objects/arrays are reduced to ids or counts by the
connector's flatten step.
"""

from __future__ import annotations

from langbridge.connectors import (
    FieldType,
    LangbridgeCatalog,
    LangbridgeField,
    LangbridgeResource,
)


def _field(name: str, field_type: FieldType, *, required: bool = False, description: str = "") -> LangbridgeField:
    return LangbridgeField(
        name=name,
        description=description or f"Shopify {name}",
        type=field_type,
        required=required,
    )


_ORDERS = LangbridgeResource(
    name="orders",
    description="Shopify orders",
    namespace="shopify",
    primary_key=["id"],
    cursor_field="updated_at",
    fields=[
        _field("id", FieldType.INTEGER, required=True, description="Order ID"),
        _field("name", FieldType.STRING, description="Order name, e.g. #1001"),
        _field("email", FieldType.STRING, description="Customer email on the order"),
        _field("created_at", FieldType.TIMESTAMP, description="When the order was created"),
        _field("updated_at", FieldType.TIMESTAMP, description="When the order was last updated"),
        _field("processed_at", FieldType.TIMESTAMP, description="When the order was processed"),
        _field("financial_status", FieldType.STRING, description="Payment status, e.g. paid, pending"),
        _field("fulfillment_status", FieldType.STRING, description="Fulfillment status"),
        _field("currency", FieldType.STRING, description="ISO currency code"),
        _field("total_price", FieldType.FLOAT, description="Order grand total"),
        _field("subtotal_price", FieldType.FLOAT, description="Order subtotal before tax and shipping"),
        _field("total_tax", FieldType.FLOAT, description="Total tax on the order"),
        _field("total_discounts", FieldType.FLOAT, description="Total discounts applied"),
        _field("customer_id", FieldType.INTEGER, description="ID of the customer who placed the order"),
        _field("line_items_count", FieldType.INTEGER, description="Number of line items on the order"),
        _field("tags", FieldType.STRING, description="Comma-separated order tags"),
        _field("cancelled_at", FieldType.TIMESTAMP, description="When the order was cancelled, if applicable"),
    ],
)

_PRODUCTS = LangbridgeResource(
    name="products",
    description="Shopify products",
    namespace="shopify",
    primary_key=["id"],
    cursor_field="updated_at",
    fields=[
        _field("id", FieldType.INTEGER, required=True, description="Product ID"),
        _field("title", FieldType.STRING, description="Product title"),
        _field("handle", FieldType.STRING, description="URL handle of the product"),
        _field("product_type", FieldType.STRING, description="Product type"),
        _field("vendor", FieldType.STRING, description="Product vendor"),
        _field("status", FieldType.STRING, description="Product status, e.g. active, draft"),
        _field("created_at", FieldType.TIMESTAMP, description="When the product was created"),
        _field("updated_at", FieldType.TIMESTAMP, description="When the product was last updated"),
        _field("published_at", FieldType.TIMESTAMP, description="When the product was published"),
        _field("tags", FieldType.STRING, description="Comma-separated product tags"),
        _field("variants_count", FieldType.INTEGER, description="Number of variants on the product"),
    ],
)

_CUSTOMERS = LangbridgeResource(
    name="customers",
    description="Shopify customers",
    namespace="shopify",
    primary_key=["id"],
    cursor_field="updated_at",
    fields=[
        _field("id", FieldType.INTEGER, required=True, description="Customer ID"),
        _field("email", FieldType.STRING, description="Customer email"),
        _field("first_name", FieldType.STRING, description="Customer first name"),
        _field("last_name", FieldType.STRING, description="Customer last name"),
        _field("created_at", FieldType.TIMESTAMP, description="When the customer was created"),
        _field("updated_at", FieldType.TIMESTAMP, description="When the customer was last updated"),
        _field("state", FieldType.STRING, description="Customer account state"),
        _field("orders_count", FieldType.INTEGER, description="Number of orders placed by the customer"),
        _field("total_spent", FieldType.FLOAT, description="Lifetime amount spent by the customer"),
        _field("tags", FieldType.STRING, description="Comma-separated customer tags"),
        _field("verified_email", FieldType.BOOLEAN, description="Whether the customer's email is verified"),
    ],
)

SHOPIFY_CATALOG = LangbridgeCatalog(
    name="shopify",
    description="Orders, products and customers from a Shopify store",
    resources=[_ORDERS, _PRODUCTS, _CUSTOMERS],
)
