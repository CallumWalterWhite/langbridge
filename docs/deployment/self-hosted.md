# Self-Hosted Deployment

Self-hosted mode runs both control and execution planes in customer-managed infrastructure.

## Minimum Services

- API
- Worker
- UI
- Postgres
- Redis

Optional:
- Qdrant
- Prometheus/Loki/Grafana

## Recommended Start

Use the core compose services:

```bash
docker compose up --build migrate api worker client db redis
```

## Operational Guidance

- Keep API and Worker versions aligned.
- Configure secrets via env/secret manager, never commit `.env` secrets.
- Tune worker concurrency with:
  - `WORKER_CONCURRENCY`
  - `WORKER_BATCH_SIZE`
- Configure federation planner knobs:
  - `FEDERATION_BROADCAST_THRESHOLD_BYTES`
  - `FEDERATION_PARTITION_COUNT`
  - `FEDERATION_STAGE_MAX_RETRIES`
  - `FEDERATION_STAGE_PARALLELISM`

## Deprecated Stack Warning

Trino and SQL gateway services present in some compose manifests are deprecated transitional components and should not be required for self-hosted production rollouts.
