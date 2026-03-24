# Langbridge Declarative Asana Connector

This package provides a thin declarative Asana workspace connector backed by the
shared `langbridge.connectors.saas.declarative` runtime.

It covers a narrow workspace slice:

- `teams`
- `projects`
- `users`

The package owns only Asana-specific manifest/config/plugin wiring plus
workspace-scoped base URL derivation. Core `langbridge` owns the declarative
manifest/runtime infrastructure.
