# Datasets

Datasets are the common structured data contract in Langbridge.

- connectors expose raw physical or external sources
- datasets define reusable technical contracts over those sources
- semantic models provide business meaning on top of datasets
- SQL, semantic, and agent execution resolve structured workloads through dataset descriptors

## Why Datasets Exist

Datasets keep execution concerns out of higher-level semantic definitions.

They capture things such as:

- source contract (`source_kind`, `connector_kind`, `storage_kind`)
- source binding (table, SQL, file, virtual, or federated metadata)
- governed schema and allowed columns
- preview and export policies
- row filters and result redaction
- canonical relation identity for federation
- execution capabilities for pushdown, materialization, and federation

## Data Model

Core records:

- `datasets`
- `dataset_columns`
- `dataset_policies`
- `dataset_revisions`
- `lineage_edges`

Datasets carry a normalized execution descriptor:

- `source_kind`
- `connector_kind`
- `storage_kind`
- `relation_identity_json`
- `execution_capabilities_json`

This lets the runtime treat database tables, files, parquet-backed syncs, and
virtual datasets as one structured execution surface.

## Versioning And Lineage

Datasets are versioned so the runtime can preserve an execution-oriented history.

Each revision stores:

- dataset definition snapshot
- schema snapshot
- policy snapshot
- source binding snapshot
- execution characteristics and relation identity

Lineage captures how datasets relate to:

- connections
- source tables
- file resources
- datasets
- semantic models

## Execution Architecture

- runtime services load dataset metadata and policies
- the worker resolves dataset descriptors and source bindings
- the federated planner executes against the normalized dataset contract
- connector secrets remain in connector or runtime secret stores

## Capability Model

Execution is driven by explicit capabilities rather than coarse dataset types.

Examples:

- `supports_structured_scan`
- `supports_sql_federation`
- `supports_filter_pushdown`
- `supports_projection_pushdown`
- `supports_aggregation_pushdown`
- `supports_join_pushdown`
- `supports_materialization`

## Direction

- treat datasets as the core structured source contract
- keep business semantics in semantic models
- keep execution metadata and source bindings in datasets
