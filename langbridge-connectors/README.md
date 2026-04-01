# Langbridge Connectors

This directory contains separately packaged connector distributions that extend
the core Langbridge runtime.

The current packaged SaaS/API connector set is:

- `langbridge-connector-stripe`
- `langbridge-connector-shopify`
- `langbridge-connector-hubspot`
- `langbridge-connector-google-analytics`
- `langbridge-connector-salesforce`
- `langbridge-connector-github`
- `langbridge-connector-jira`
- `langbridge-connector-asana`

These packages stay intentionally thin. Some are manifest-driven and use the
shared declarative runtime under `langbridge.connectors.saas.declarative`;
others package custom connector logic where the runtime behavior is not yet a
good declarative fit.
