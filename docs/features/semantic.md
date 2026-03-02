# Semantic Feature

Langbridge semantic modeling provides governed analytical structure for agent and BI workloads.

## Capabilities

- Canonical semantic model schema.
- Semantic model CRUD and YAML retrieval.
- Semantic query APIs for measure/dimension workflows.
- Unified semantic datasets with federation workflow bindings.
- Integration with BI Studio and agent tools.

## Runtime Behavior

- Semantic queries are orchestrated by control plane.
- Execution is dispatched to worker.
- Worker uses federated planner/executor for multi-source plans.

## Key APIs

- `/api/v1/semantic-model/*`
- `/api/v1/semantic-query/{semantic_model_id}/meta`
- `/api/v1/semantic-query/{semantic_model_id}/q`

## Related Docs

- `docs/semantic-model.md`
- `docs/features/federation.md`
