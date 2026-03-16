# Worker Development

## Worker Role

The runtime worker executes:

- SQL jobs
- semantic query jobs
- dataset preview, profile, and ingest jobs
- connector sync jobs
- agent and analytical runtime jobs

## Run Worker

```bash
python -m langbridge.apps.runtime_worker.main
```

Reload mode:

```bash
python -m langbridge.apps.runtime_worker.main --reload
```

## Key Environment Variables

- `WORKER_CONCURRENCY`
- `WORKER_BATCH_SIZE`
- `WORKER_POLL_INTERVAL`
- `WORKER_BROKER`
- `FEDERATION_ARTIFACT_DIR`
- `FEDERATION_BROADCAST_THRESHOLD_BYTES`
- `FEDERATION_PARTITION_COUNT`
- `FEDERATION_STAGE_MAX_RETRIES`
- `FEDERATION_STAGE_PARALLELISM`

## Main Code Paths

- runtime loop: `langbridge/apps/runtime_worker/main.py`
- dispatcher: `langbridge/apps/runtime_worker/handlers/dispatcher.py`
- SQL job handler: `langbridge/apps/runtime_worker/handlers/query/sql_job_request_handler.py`
- semantic handler: `langbridge/apps/runtime_worker/handlers/query/semantic_query_request_handler.py`
- federated tool: `langbridge/packages/runtime/execution/federated_query_tool.py`
