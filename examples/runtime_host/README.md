# Runtime Host Example

This example shows how to self-host the Langbridge runtime as an HTTP API instead of
running the worker app.

The container starts the runtime with the CLI entrypoint:

```bash
langbridge serve --config /examples/runtime_host/langbridge_config.yml --host 0.0.0.0 --port 8000
```

It uses a mounted runtime config rather than baking configuration into the image. The
config in this folder points at the seeded SQLite demo warehouse from the SDK example.

## What This Example Gives You

- a Dockerized runtime host process
- mounted runtime configuration at `/examples/runtime_host/langbridge_config.yml`
- mounted demo SQLite warehouse from `examples/sdk/semantic_query/example.db`
- persistent local runtime state under `/examples/runtime_host/.langbridge`
- HTTP APIs for dataset preview, semantic query, SQL query, and agent calls

## Prerequisites

From the repository root, seed the demo database once:

```bash
python examples/sdk/semantic_query/setup.py
```

If you want to exercise the agent endpoint, export an LLM key before starting the
container:

```bash
export OPENAI_API_KEY=...
```

## Start The Runtime Host

From this directory:

```bash
docker compose up --build
```

The runtime host will listen on `http://localhost:8000`.

## Mounted Files

The compose file mounts:

- `../` to `/examples`
- a named Docker volume to `/examples/runtime_host/.langbridge`

That means:

- connector and dataset paths still resolve correctly because they stay relative to the
  mounted config file
- runtime metadata and DuckDB execution state persist across container restarts
- you can swap in your own config later without rebuilding the image

## Try The API

Check the host:

```bash
curl http://localhost:8000/api/runtime/v1/health
```

List configured datasets:

```bash
curl http://localhost:8000/api/runtime/v1/datasets
```

Preview a dataset:

```bash
curl -X POST http://localhost:8000/api/runtime/v1/datasets/shopify_orders/preview \
  -H "Content-Type: application/json" \
  -d '{"limit": 5}'
```

Run a semantic query:

```bash
curl -X POST http://localhost:8000/api/runtime/v1/semantic/query \
  -H "Content-Type: application/json" \
  -d '{
    "semantic_models": ["commerce_performance"],
    "measures": ["shopify_orders.net_sales"],
    "dimensions": ["shopify_orders.country"],
    "order": [{"member": "shopify_orders.net_sales", "direction": "desc"}],
    "limit": 5
  }'
```

Run a direct SQL query:

```bash
curl -X POST http://localhost:8000/api/runtime/v1/sql/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "SELECT country, SUM(net_revenue) AS net_sales FROM orders_enriched GROUP BY country ORDER BY net_sales DESC LIMIT 5",
    "connection_name": "commerce_demo"
  }'
```

Ask the default analytics agent:

```bash
curl -X POST http://localhost:8000/api/runtime/v1/agents/ask \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Which countries have the highest net sales this quarter?"
  }'
```

## Run The Same Host Without Docker

If you install Langbridge locally, the host command is the same shape:

```bash
pip install langbridge
python examples/sdk/semantic_query/setup.py
langbridge serve --config examples/runtime_host/langbridge_config.yml --host 0.0.0.0 --port 8000
```

You can also use the module entrypoint:

```bash
python -m langbridge serve --config examples/runtime_host/langbridge_config.yml --host 0.0.0.0 --port 8000
```

Once the host is up, the CLI can call the same APIs:

```bash
langbridge info --url http://localhost:8000
langbridge datasets list --url http://localhost:8000
langbridge semantic query --url http://localhost:8000 --model commerce_performance --measure shopify_orders.net_sales --dimension shopify_orders.country --limit 5
```

## Notes

- This example intentionally hosts the portable runtime only. It does not depend on the
  cloud control plane.
- The example bind-mounts the repository `examples/` tree and overlays a named volume on
  `/examples/runtime_host/.langbridge` so the host can maintain local metadata and
  execution artifacts without polluting the checked-in files.
- If you replace the mounted config, keep any relative connector and storage paths valid
  from the config file location.
