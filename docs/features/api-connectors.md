# API Connector Sync

Langbridge API connectors materialize SaaS or API data into runtime-managed
datasets instead of querying third-party APIs live during federated execution.

## Architecture

`API Connector -> Sync Job -> Normalize / Flatten -> Runtime Dataset`

Key implementation points:

- sync execution runs in the worker through connector sync jobs
- resumable state is tracked per synced resource
- normalized outputs can be written as parquet-backed datasets
- nested arrays can be materialized as child datasets
- dataset metadata keeps sync provenance in file or connector metadata

## Sync Modes

- `FULL_REFRESH`: replace the materialized dataset contents
- `INCREMENTAL`: resume from the last successful cursor when supported

## Why This Model Exists

- runtime federation works best over stable structured datasets
- sync decouples third-party API behavior from query-time execution
- semantic, SQL, and agent workloads can all consume the same normalized dataset surface
