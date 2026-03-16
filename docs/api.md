# Runtime Interfaces

Langbridge exposes runtime functionality through a small number of public surfaces.

This repository documents the runtime-facing interfaces rather than any product-specific
application API.

## Main Runtime Surfaces

- Python packages under `langbridge/packages/*`
- worker assembly in `langbridge/apps/runtime_worker`
- runtime contracts in `langbridge/packages/contracts`
- semantic model contract in `docs/semantic-model.md`
- dataset contract in `docs/datasets.md`

## Interface Categories

### Embedded Python Use

Use the runtime packages directly when you want to embed Langbridge into an
application or service.

Typical areas include:

- connector access
- semantic execution
- federated execution
- dataset operations
- agent-style runtime execution

### Worker Runtime

Use the runtime worker when you want Langbridge to execute queued or delegated work
as a standalone runtime process.

The worker is the main execution surface for:

- SQL jobs
- semantic query jobs
- dataset preview and profile jobs
- connector sync jobs
- agent and analytical runtime jobs

### Contracts And Schemas

Published runtime contracts should stay explicit and versionable.

The most important runtime contracts are:

- dataset request and result payloads
- SQL and semantic execution payloads
- runtime-safe job contracts
- semantic model schema

## Related Docs

- `docs/semantic-model.md`
- `docs/datasets.md`
- `docs/architecture/execution-plane.md`
- `docs/features/sql.md`
- `docs/features/semantic.md`
