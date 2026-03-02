# Federation Feature

Federation in Langbridge is the built-in distributed planning and execution capability for cross-source workloads.

## What Federation Does

- Maps virtual datasets to connectors/sources.
- Parses SQL or compiled semantic SQL into logical plans.
- Optimizes and emits physical stage DAGs.
- Executes remote scans and local compute stages.
- Produces result handles and artifacts for API/UI retrieval.

## Where It Runs

- Runs in Worker execution plane.
- Uses `langbridge/packages/federation` planner and executor modules.
- Uses connector abstractions from `langbridge/packages/connectors`.

## Why It Matters

- No external SQL gateway is required.
- Single execution substrate for semantic + SQL workloads.
- Works in hosted and customer runtime modes.

## Explainability

Federation exposes explain data:
- Logical plan.
- Physical plan.
- Stage-level execution metadata.

See `docs/architecture/federated-query-engine.md` for DAG details.
