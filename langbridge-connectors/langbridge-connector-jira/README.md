# Langbridge Declarative Jira Connector

This package provides a thin declarative Jira Cloud connector backed by the
shared `langbridge.connectors.saas.declarative` runtime.

It covers a narrow admin/metadata slice:

- `projects`
- `fields`
- `statuses`

The package owns only Jira-specific manifest/config/plugin wiring plus cloud-ID
base URL derivation. Core `langbridge` owns the declarative manifest/runtime
infrastructure.
