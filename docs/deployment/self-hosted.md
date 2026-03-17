# Self-Hosted Deployment

Self-hosted deployment means running the Langbridge runtime in your own environment.

Langbridge currently has two self-hosted runtime shapes:

- runtime worker stack for queue-backed execution
- runtime API host for serving a configured local runtime over HTTP

## Runtime API Host

The current runtime host release wraps a configured local runtime and exposes:

- `GET /api/runtime/v1/health`
- `GET /api/runtime/v1/info`
- `GET /api/runtime/v1/datasets`
- `POST /api/runtime/v1/datasets/{dataset_id}/preview`
- `GET /api/runtime/v1/connectors`
- `GET /api/runtime/v1/connectors/{connector_name}/sync/resources`
- `GET /api/runtime/v1/connectors/{connector_name}/sync/states`
- `POST /api/runtime/v1/connectors/{connector_name}/sync`
- `POST /api/runtime/v1/semantic/query`
- `POST /api/runtime/v1/sql/query`
- `POST /api/runtime/v1/agents/ask`
- interactive docs at `/api/runtime/docs`

### Start With Pip And The CLI

From the repository root:

```bash
python examples/sdk/semantic_query/setup.py
python -m venv .venv
source .venv/bin/activate
pip install -e .
langbridge serve --config examples/sdk/semantic_query/langbridge_config.yml --host 127.0.0.1 --port 8000
```

If you want to call the configured demo agent, export `OPENAI_API_KEY` before starting
the host.

You can then exercise the host with the same CLI:

```bash
langbridge info --url http://127.0.0.1:8000
langbridge datasets list --url http://127.0.0.1:8000
```

### Start With Docker

From the repository root:

```bash
python examples/sdk/semantic_query/setup.py
docker compose --profile host up --build runtime-host
```

That profile uses `langbridge/Dockerfile.host` plus the existing
`examples/sdk/semantic_query/` config and database. The host stays portable and
config-driven; it does not require Postgres or Redis for this example.

For a folder-scoped example, see `examples/runtime_host/`.

## Worker Stack

- worker runtime
- Postgres
- Redis

Optional:

- Qdrant

For a lighter self-hosted shape, you can run the portable runtime host directly and expose
its HTTP API without the worker app. This is the better fit when you want SDK-style dataset,
semantic, SQL, and agent APIs over a configured local/self-hosted runtime.

## Recommended Start

```bash
docker compose up --build db redis worker
```

## Runtime Host Mode

To host the runtime directly from an installed package:

```bash
pip install langbridge
langbridge serve --config /path/to/langbridge_config.yml --host 0.0.0.0 --port 8000
```

Or with the module entrypoint:

```bash
python -m langbridge serve --config /path/to/langbridge_config.yml --host 0.0.0.0 --port 8000
```

The hosted API exposes runtime-owned endpoints under `/api/runtime/v1/` for:

- dataset listing and preview
- connector discovery and hosted sync operations
- semantic queries
- SQL queries
- agent asks

For containerized walkthroughs, use:

- `examples/runtime_host/` for dataset, semantic, SQL, and agent APIs
- `examples/runtime_host_sync/` for hosted connector sync plus managed dataset materialization

If you want sync state and managed datasets to remain available across commands, run the
runtime as a long-lived host process or container and persist its mounted state. Repeated
one-shot `langbridge ... --config ...` invocations rebuild the configured local runtime in
memory each time.

## Operational Guidance

- keep runtime package versions aligned
- configure secrets through environment variables or a secret manager
- tune worker behavior with `WORKER_CONCURRENCY`, `WORKER_BATCH_SIZE`, and `WORKER_POLL_INTERVAL`
- tune federation with `FEDERATION_BROADCAST_THRESHOLD_BYTES`, `FEDERATION_PARTITION_COUNT`, `FEDERATION_STAGE_MAX_RETRIES`, and `FEDERATION_STAGE_PARALLELISM`
