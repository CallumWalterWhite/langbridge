# Federation Feature

Federation is Langbridge's built-in planning and execution capability for
cross-source structured workloads.

## What Federation Does

- maps datasets to connectors and source bindings
- parses SQL or compiled semantic SQL into logical plans
- optimizes and emits physical stage DAGs
- executes remote scans and local compute stages
- produces result rows, artifacts, and execution metadata

## Where It Runs

- in the runtime worker
- through `langbridge/packages/federation`
- using connector abstractions from `langbridge/packages/connectors`

## Why It Matters

- no separate SQL gateway is required
- semantic and SQL workloads share one structured execution substrate
- cross-source joins and transformations stay inside the runtime

## Explainability

Federation can expose:

- logical plan data
- physical plan data
- stage-level execution metadata

See `docs/architecture/federated-query-engine.md` for more detail.
