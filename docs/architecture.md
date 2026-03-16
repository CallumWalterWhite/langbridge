# Architecture

Langbridge is a runtime for executing data-aware workloads across connectors,
datasets, semantic models, and federated plans.

At a high level, the runtime is made of:

- a connector layer for reaching data systems
- a dataset layer for normalizing structured sources
- a semantic layer for business-facing analytical structure
- a federated engine for planning and executing cross-source workloads
- a worker/runtime host for executing jobs and runtime tasks

## Read Next

- `docs/architecture/overview.md`
- `docs/architecture/execution-plane.md`
- `docs/architecture/federated-query-engine.md`
- `docs/architecture/hybrid-deployment.md`
- `docs/architecture/runtime-boundary.md`
- `docs/architecture/dataset-federation-upgrade.md`
