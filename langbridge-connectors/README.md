# Langbridge Connectors

This directory contains separately packaged connector distributions that extend
the core Langbridge runtime.

The current declarative SaaS/API package set is:

- `langbridge-connector-stripe`
- `langbridge-connector-shopify`
- `langbridge-connector-hubspot`
- `langbridge-connector-github`
- `langbridge-connector-jira`
- `langbridge-connector-asana`

These packages stay intentionally thin. Core `langbridge` owns the shared
declarative manifest schema, config derivation helpers, dataset example loader,
and manifest-driven HTTP execution runtime under
`langbridge.connectors.saas.declarative`.
