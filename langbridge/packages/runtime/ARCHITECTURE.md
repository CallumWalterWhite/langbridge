# Runtime Architecture Notes

## Direction

The runtime package is being migrated toward runtime-owned boundaries:

- runtime-native models in `packages/runtime/models`
- runtime-native ports in `packages/runtime/ports`
- backend adapters that translate legacy repository and API payloads into those runtime models

This is intended to reduce direct coupling from `packages/runtime` into:

- `packages/contracts`
- `packages/common/langbridge_common`

## Modes

The target runtime modes are:

- `local_ephemeral`
  - config-backed metadata
  - in-memory runtime state
- `local_persistent`
  - local persistent control store, initially SQLite-backed
- `hybrid`
  - control-plane API backed metadata/state
- managed cloud
  - composed in `langbridge-cloud`, not in the portable runtime package

## Transitional Rules

During migration:

- read-oriented runtime services should prefer runtime ports
- write-heavy services may continue using legacy repositories until explicit command ports are introduced
- compatibility adapters in `packages/runtime/adapters` are allowed to depend on legacy repository and API shapes
- new runtime internals should not add fresh dependencies on `packages/contracts` unless they are true external API contracts

## Current First Slice

The first migration slice introduces:

- runtime-native metadata/state models
- runtime-owned job/request models that preserve worker payload compatibility
- runtime ports replacing contract-typed provider boundaries
- repository-backed and API-backed providers returning runtime-native models
- real in-memory providers for ephemeral mode work

Follow-on slices should move more services to runtime-native models and shrink the remaining direct `common` and `contracts` imports.
