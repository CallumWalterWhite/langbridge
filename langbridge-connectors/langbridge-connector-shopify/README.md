# Langbridge Declarative Shopify Connector

This package provides a thin declarative Shopify Admin connector backed by the
shared `langbridge.connectors.saas.declarative` runtime.

It covers a narrow commerce slice:

- `customers`
- `draft_orders`
- `locations`

The package owns only Shopify-specific manifest/config/plugin wiring plus
shop-domain base URL derivation. Core `langbridge` owns the declarative runtime.
