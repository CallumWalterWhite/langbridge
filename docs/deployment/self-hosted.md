# Self-Hosted Deployment

Self-hosted deployment means running the Langbridge runtime in your own environment.

## Typical Services

Minimum runtime services:

- worker runtime
- Postgres
- Redis

Optional:

- Qdrant

## Recommended Start

```bash
docker compose up --build db redis worker
```

## Operational Guidance

- keep runtime package versions aligned
- configure secrets through environment variables or a secret manager
- tune worker behavior with:
  - `WORKER_CONCURRENCY`
  - `WORKER_BATCH_SIZE`
  - `WORKER_POLL_INTERVAL`
- tune federation with:
  - `FEDERATION_BROADCAST_THRESHOLD_BYTES`
  - `FEDERATION_PARTITION_COUNT`
  - `FEDERATION_STAGE_MAX_RETRIES`
  - `FEDERATION_STAGE_PARALLELISM`
