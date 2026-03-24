# Langbridge Declarative GitHub Connector

This package provides a thin declarative GitHub REST connector backed by the
shared `langbridge.connectors.saas.declarative` runtime.

It covers a narrow authenticated-user slice:

- `repositories`
- `issues`
- `notifications`

The package supplies only GitHub-specific manifest/config/plugin data. Core
`langbridge` owns the declarative manifest contract and HTTP execution runtime.
