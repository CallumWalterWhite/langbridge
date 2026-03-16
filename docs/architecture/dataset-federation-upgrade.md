# Dataset Federation Upgrade

## Current Direction

Langbridge is moving from coarse dataset typing toward a normalized dataset
execution contract.

Today, legacy dataset types such as `TABLE`, `SQL`, `FILE`, and `FEDERATED`
still exist for compatibility, but the runtime is increasingly driven by richer
execution descriptors.

## What Is Changing

- add a first-class dataset contract across runtime metadata
- normalize datasets around:
  - `source_kind`
  - `connector_kind`
  - `storage_kind`
  - `relation_identity`
  - `execution_capabilities`
- refactor runtime and federation entrypoints to consume those normalized descriptors

## Why It Matters

- parquet-backed syncs and files can behave like structured joinable datasets
- database tables, files, and virtual datasets can share one execution surface
- planner and runtime code can reason about capabilities instead of source-specific branches

## Expected Outcome

- the runtime becomes more dataset-first
- structured execution becomes easier to extend
- federation works across more source types without bespoke logic
