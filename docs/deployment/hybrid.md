# Hybrid Deployment

Hybrid deployment runs the Langbridge runtime in customer-managed infrastructure
while allowing integration with external orchestration or metadata systems.

## Typical Shape

- the runtime worker runs close to customer data
- connectors and secrets stay in the customer environment
- external systems interact with the runtime through explicit contracts

## Runtime Setup

Start the runtime worker with the same core runtime configuration used for
self-hosted deployments, then add any external integration settings required by
your environment.

Useful runtime variables:

- `WORKER_CONCURRENCY`
- `WORKER_BATCH_SIZE`
- `WORKER_BROKER`
- `FEDERATION_ARTIFACT_DIR`

## Integration Guidance

- keep external integration boundaries explicit
- do not let external orchestration logic leak into core runtime packages
- prefer versioned schemas, clients, or message contracts over ad hoc coupling
