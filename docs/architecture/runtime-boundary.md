# Runtime Boundary

## Purpose

`langbridge/` is the runtime repository.

Its job is to produce portable execution capabilities that work in:

- local development
- embedded Python use
- self-hosted deployments
- hybrid enterprise deployments

## What Belongs In This Repository

Code belongs in `langbridge/` when it is required to execute workloads even if
no separate hosted product exists.

This includes:

- runtime host and execution APIs
- semantic execution
- federated planning and execution
- connectors
- dataset execution primitives
- runtime-safe agent execution primitives
- local runtime configuration
- reusable runtime libraries and packages
- versioned runtime contracts and schemas

## What Does Not Belong Here

This repository should avoid application surfaces that primarily exist to manage
or deliver a hosted product experience.

Examples include:

- application UIs
- application-level user or organization management
- product-auth-specific application logic
- hosted orchestration glue that is not required by the runtime itself
- operational tooling that is only meaningful for a hosted control layer

## Target Shape

The runtime repo should continue moving toward a package-oriented structure:

```text
langbridge/
  packages/
    contracts/
    runtime/
    semantic/
    federation/
    connectors/
    ...
  apps/
    runtime_worker/
  docs/
```

## Package Direction

- core logic should live in packages
- assembly apps should stay thin
- runtime surfaces should remain portable
- interfaces should be explicit and versionable

## Definition Of Done

The runtime boundary is healthy when:

- runtime logic is portable and reusable
- docs describe the runtime without depending on private product surfaces
- runtime packages do not depend on private app code
- public concepts are expressed as contracts and packages rather than hidden integrations
