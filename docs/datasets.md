# Datasets

Datasets are Langbridge's structured execution contract.

They sit between connectors and higher-level query surfaces:

- connectors expose source-specific access
- datasets normalize those sources into workspace-scoped runtime metadata
- semantic, SQL, sync, and agent workloads resolve through datasets

## Why Datasets Exist

Datasets let the runtime work with one structured concept even when the backing
source differs.

They capture:

- workspace ownership
- source binding
- relation identity
- execution capabilities
- schema and policy metadata
- lineage and revision history

## Runtime Shape

The runtime dataset metadata model lives in `langbridge/runtime/models/metadata.py`
and centers on:

- `workspace_id`
- `connection_id`
- `name`
- `sql_alias`
- `dataset_type`
- `materialization_mode`
- `source_kind`
- `connector_kind`
- `storage_kind`
- `relation_identity`
- `execution_capabilities`
- `columns`
- `policy`

Important supporting records:

- `DatasetMetadata`
- `DatasetColumnMetadata`
- `DatasetPolicyMetadata`
- `DatasetRelationIdentity`
- `DatasetExecutionCapabilities`

## Dataset Mode

Dataset behavior is now dataset-owned through `materialization_mode`:

- `live`
- `synced`

That field is part of the canonical runtime dataset model and the configured
runtime config model.

The runtime validates each dataset definition against connector capabilities
instead of assuming behavior from connector family alone.

Examples:

- a SQLite or Postgres dataset can be `live`
- a runtime-managed dataset intentionally created through the runtime can be `synced`
- a config-defined synced connector resource path can be declared in YAML and populated later by dataset sync
- a connector may eventually support both modes, but only if the runtime has a real execution path for each

## Workspace Scope

Datasets are resolved per workspace. That is the runtime boundary that matters
for execution. Runtime-core dataset resolution does not depend on upstream
product-account identity claims.

## Source Types

Datasets may represent:

- database tables
- SQL-defined virtual datasets
- file-backed datasets
- sync-materialized datasets
- federated or derived datasets

## Connector Capabilities

The runtime keeps connector kind separate from capability flags. Dataset mode
validation currently relies on connector capability metadata such as:

- `supports_live_datasets`
- `supports_synced_datasets`
- `supports_incremental_sync`
- `supports_query_pushdown`
- `supports_preview`
- `supports_federated_execution`

A dataset requesting `materialization_mode: live` must use a connector that
supports live datasets. A dataset requesting `materialization_mode: synced`
must use a connector that supports synced datasets. Config-defined synced
datasets currently require a runtime sync-capable connector and use
`sync.source` as the dataset-owned source contract to materialize.

## API Resource Paths

For API-backed datasets, the dataset owns the selected resource path.

- `sync.source.resource: orders` materializes the parent resource
- `sync.source.resource: orders.line_items` materializes an explicit child resource path
- `sync.source.resource: accounts.owner` materializes an explicit 1:1 child object as its own dataset

The runtime does not create additional datasets just because a connector
discovers nested children during sync. A dataset only exists when it is:

- declared in config
- or intentionally created through the runtime dataset APIs

## Explicit Flattening

API flattening is dataset-owned through `sync.source.flatten` or `source.flatten`.

- flattening is only valid for resource-backed API datasets
- flattening is explicit, not inferred from connector discovery
- only 1:1 child objects may be flattened into the parent dataset
- 1:many children are never flattened into the parent dataset and never silently materialized as sibling datasets

Example:

```yaml
datasets:
  - name: billing_customers
    connector: billing_demo
    materialization_mode: synced
    sync:
      source:
        resource: customers
        flatten:
          - default_address
```

## Scheduled Sync

Synced datasets can register background sync directly from their dataset-owned
sync contract.

Supported fields:

- `sync.cadence`
- `sync.sync_on_start`

Supported cadence format in this slice:

- interval shorthands only: `30s`, `5m`, `1h`, `1d`

Example:

```yaml
datasets:
  - name: billing_customers
    connector: billing_demo
    materialization_mode: synced
    sync:
      source:
        resource: customers
      cadence: 1h
      sync_on_start: true
```

Behavior:

- the runtime host registers a background task named `dataset-sync:<dataset-name>`
- the scheduled handler runs dataset-owned sync through `sync_dataset(dataset_ref=...)`
- `sync_on_start: true` triggers one sync during runtime startup even when no cadence is set
- invalid cadence values are rejected during config/runtime model validation with a
  message pointing to the supported shorthand format

## Policies And Guardrails

Dataset policy is where the runtime applies:

- preview row limits
- export limits
- redaction rules
- row filters
- DML permissions

That policy is reused across dataset preview, SQL, semantic, and agent-driven
execution.

## Current Direction

Langbridge is moving toward a richer dataset-first execution model driven by
relation identity, explicit materialization mode, and execution capabilities
rather than coarse dataset types or connector families alone.
