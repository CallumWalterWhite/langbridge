# Runtime Host Sync Example

This example starts a self-hosted Langbridge runtime host alongside a local
Stripe-like mock API and syncs the `customers` resource into a runtime-managed
dataset. It is scoped to this folder only: the compose stack mounts this folder,
keeps runtime state in named volumes, and does not depend on Langbridge Cloud.

The runtime host uses the current host image and CLI shape:

```bash
python -m langbridge serve --config /example/langbridge_config.yml --host 0.0.0.0 --port 8000
```

## What This Example Starts

- `runtime-host`: the existing self-hosted runtime host image from `langbridge/Dockerfile.host`
- `mock-stripe`: a local HTTP API that exposes `/v1/account` and `/v1/customers`

## Files In This Folder

- `docker-compose.yml`: starts the runtime host plus the mock Stripe service
- `langbridge_config.yml`: self-hosted runtime config with a `stripe` connector
- `mock_stripe.py`: local Stripe-like API used for sync testing
- `README.md`: walkthrough for connector discovery, sync, state inspection, and dataset preview

## Prerequisites

- Docker
- Docker Compose v2

## Start The Stack

From this directory:

```bash
docker compose up --build -d
```

The services listen on:

- runtime host: `http://localhost:8000`
- mock Stripe API: `http://localhost:12111`

## Check Health

```bash
curl http://localhost:12111/health
curl http://localhost:8000/api/runtime/v1/health
```

## Inspect Connectors And Sync Resources

List configured connectors:

```bash
curl http://localhost:8000/api/runtime/v1/connectors
```

List syncable resources for the Stripe connector:

```bash
curl http://localhost:8000/api/runtime/v1/connectors/billing_demo/sync/resources
```

You should see `customers` with `status` set to `never_synced`.

## Run A Sync

```bash
SYNC_RESPONSE=$(curl -s -X POST http://localhost:8000/api/runtime/v1/connectors/billing_demo/sync \
  -H "Content-Type: application/json" \
  -d '{
    "resource_names": ["customers"],
    "sync_mode": "INCREMENTAL"
  }')

printf '%s\n' "$SYNC_RESPONSE"
```

The sync response includes the runtime-managed dataset name in
`resources[0].dataset_names[0]`.

## Inspect Sync State

```bash
curl http://localhost:8000/api/runtime/v1/connectors/billing_demo/sync/states
```

## List And Preview The Synced Dataset

List datasets:

```bash
curl http://localhost:8000/api/runtime/v1/datasets
```

Preview the dataset returned by the sync response:

```bash
DATASET_NAME=$(printf '%s' "$SYNC_RESPONSE" | python -c "import json,sys; print(json.load(sys.stdin)['resources'][0]['dataset_names'][0])")

curl -X POST "http://localhost:8000/api/runtime/v1/datasets/${DATASET_NAME}/preview" \
  -H "Content-Type: application/json" \
  -d '{"limit": 5}'
```

## Use The Runtime CLI Against The Hosted API

If `langbridge` is installed locally, the same runtime host can be exercised with
the current CLI:

```bash
langbridge connectors list --url http://localhost:8000
langbridge sync resources --url http://localhost:8000 --connector billing_demo
langbridge sync run --url http://localhost:8000 --connector billing_demo --resource customers
langbridge sync states --url http://localhost:8000 --connector billing_demo
langbridge datasets list --url http://localhost:8000
langbridge datasets preview --url http://localhost:8000 --dataset "$DATASET_NAME" --limit 5
```

## Notes

- The runtime config intentionally defines only a portable local runtime plus a
  Stripe connector. No cloud control plane or hosted orchestration is involved.
- The compose stack mounts only this folder and keeps `.langbridge` plus synced
  dataset artifacts in named Docker volumes so the repository does not get
  polluted with runtime state.
- If you want to stop and remove all persisted example state, run:

```bash
docker compose down -v
```
