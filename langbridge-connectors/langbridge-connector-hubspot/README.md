# Langbridge HubSpot Connector

This package owns the HubSpot connector plugin for Langbridge.

It keeps the connector package thin while preserving the runtime behavior that
used to live in core `langbridge`.

Supported resources:

- `contacts`
- `companies`
- `deals`
- `tickets`

The package still uses core `langbridge.connectors.saas.declarative` runtime
infrastructure, but now owns the HubSpot-specific manifest, config compatibility
surface, and plugin registration.
