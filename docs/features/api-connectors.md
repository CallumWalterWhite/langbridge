# Connectors, Plugins, And Sync

Langbridge uses a plugin-style connector model.

## Structure

- connector interfaces and registration live under `langbridge.plugins`
- built-in connectors live under `langbridge.connectors`
- external connector packages can register through entry points

This keeps connector extension runtime-owned while allowing separate
distribution of connector packages where needed.

## Runtime Direction

Connector kind, connector capabilities, and dataset mode are separate concerns:

- connector kind describes the source family, such as `database`, `api`, `file`, or `vector`
- connector capabilities describe what the connector can actually do
- dataset `materialization_mode` describes whether a specific dataset is `live` or `synced`

The runtime now validates dataset mode against connector capabilities instead of
inferring behavior from connector family alone.

Current connector capabilities include:

- `supports_live_datasets`
- `supports_synced_datasets`
- `supports_incremental_sync`
- `supports_query_pushdown`
- `supports_preview`
- `supports_federated_execution`

Today that means:

- SQL connectors expose live datasets
- file connectors expose live file-backed datasets
- API/SaaS sync connectors expose synced datasets through the runtime sync flow

The long-term product direction remains broader than the currently implemented
matrix. A connector may eventually support one or both of live and synced
datasets, but the runtime is explicit about what is supported right now.

## Runtime-Owned Sync

Runtime sync is owned by datasets and exposed through runtime host
endpoints. The current self-hosted host supports:

- connector listing
- syncable resource discovery
- sync state inspection
- dataset sync execution

The resulting datasets stay inside the runtime execution model.

The V1 sync model is dataset-owned and explicit:

- connector discovery reports resource structure, but does not create datasets
- sync only materializes datasets that already exist in config or were intentionally created through runtime dataset APIs
- live API datasets use `source.resource` and `source.flatten`
- synced API datasets use `sync.source.resource` and `sync.source.flatten`
- resource paths use canonical dot-separated names such as `orders`, `orders.line_items`, or `accounts.owner`
- 1:many children are never flattened and never silently turned into sibling datasets

## Declarative SaaS Connector Ownership

The declarative SaaS connector contract belongs in core `langbridge` under
`langbridge.connectors.saas.declarative`.

Core owns:

- manifest models and schema validation
- manifest loading helpers
- shared auth/config-schema derivation helpers
- manifest-driven HTTP execution for SaaS/API connectors that currently feed the synced dataset path

The current declarative runtime slice is intentionally narrow and runtime-first:

- package manifests define auth, pagination, incremental cursor rules, resource inventory, and connector capability metadata
- core `langbridge` turns that manifest into an executable `ApiConnector`
- the runtime sync flow materializes declared resource paths into datasets with `materialization_mode: synced`
- live API datasets can now execute honestly as dataset-declared live sources by fetching resource data into DuckDB-backed local federation

The declarative runtime now covers multiple common SaaS API patterns:

- bearer-token and header-token auth with optional static headers
- per-resource response item paths and default request params
- record-derived cursors, response-derived cursors, Link-header cursors, and offset pagination
- request-param incremental sync and client-side incremental filtering for APIs without a native incremental filter

This is enough for real manifest-defined SaaS sync without forcing every connector into the declarative model.

## Current Support Matrix

The runtime is intentionally honest about what it supports today:

- config-defined SQL datasets: supported with `materialization_mode: live`
- config-defined file datasets: supported with `materialization_mode: live`
- config-defined synced API datasets: supported with `materialization_mode: synced` and `sync.source.resource` naming the resource path
- config-defined synced SQL datasets: supported with `materialization_mode: synced` and either `sync.source.table` or `sync.source.sql`
- runtime-managed datasets intentionally created through the runtime: supported with `materialization_mode: synced`
- config-defined synced datasets without a runtime sync path: not supported yet
- live API/SaaS datasets: supported when the connector exposes a runtime API execution path; Langbridge fetches the dataset-declared API resource into local DuckDB execution rather than pretending SQL pushdown exists

Example synced datasets:

```yaml
datasets:
  - name: shopify_customers
    connector: shopify_demo
    materialization_mode: synced
    sync:
      source:
        resource: customers
        flatten:
          - default_address

  - name: shopify_product_options
    connector: shopify_demo
    materialization_mode: synced
    sync:
      source:
        resource: products.options
```

Connector packages under `langbridge-connectors` should stay thin and primarily
provide package-owned config/schema/plugin wiring plus either:

- manifest files that point at the core declarative runtime
- package-owned connector logic where the runtime behavior is not yet a clean declarative fit

Where a connector package exists, the runtime should resolve that package as the
authoritative connector implementation. Core `langbridge` now retains only the
shared SaaS runtime contracts and declarative execution helpers.

## Current Declarative Connector Packages

The current package set under `langbridge-connectors` is:

- `langbridge-connector-stripe`
- `langbridge-connector-shopify`
- `langbridge-connector-hubspot`
- `langbridge-connector-google-analytics`
- `langbridge-connector-salesforce`
- `langbridge-connector-github`
- `langbridge-connector-jira`
- `langbridge-connector-asana`

These packages prove the same runtime contract across several SaaS API shapes
without re-implementing manifest loading or HTTP sync execution in each package.

Asana is used in this slice instead of Notion because the current declarative
runtime remains intentionally GET/query-param oriented; richer body-driven APIs
such as Notion search and database query flows are still later work.
