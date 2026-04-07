# Langbridge Shopify Connector

This package owns the Shopify connector plugin for Langbridge.

It preserves the runtime-owned sync behavior that previously lived in core
`langbridge` while loading through the package/plugin surface.

Supported resources:

- `orders`
- `customers`
- `products`

The package supports either:

- a direct Shopify Admin API access token
- the legacy Shopify app client id/client secret flow

It still uses the shared `langbridge.connectors.saas.declarative` runtime for
manifest-driven HTTP execution, but owns the Shopify-specific auth and config
compatibility layer.
