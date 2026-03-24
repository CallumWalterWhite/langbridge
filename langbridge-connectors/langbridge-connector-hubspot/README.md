# Langbridge Declarative HubSpot Connector

This package provides a thin declarative HubSpot CRM connector backed by core
`langbridge.connectors.saas.declarative` runtime infrastructure.

It covers a narrow but practical CRM slice:

- `contacts`
- `companies`
- `deals`

The package owns only HubSpot-specific manifest/config/plugin wiring. Core
`langbridge` owns manifest validation, auth/config helpers, and declarative HTTP
runtime execution.
