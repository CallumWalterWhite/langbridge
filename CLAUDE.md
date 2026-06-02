# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

**Setup (Windows PowerShell):**
```powershell
python -m venv .venv && .\.venv\Scripts\activate && pip install -r requirements/dev.txt && pip install -e .
```

**Run runtime host:**
```bash
langbridge serve --config examples/deployment/runtime_host/langbridge_config.yml
langbridge serve --config examples/deployment/runtime_host/langbridge_config.yml --features ui,mcp
```

**Tests:**
```bash
pytest -q tests                        # full suite
pytest -q tests/unit                   # unit tests only
pytest -q tests/federation             # federation engine
pytest -q tests/semantic               # semantic layer
pytest -q tests/integration            # multi-component
pytest -q tests -m "not slow"          # skip slow tests
pytest -q tests/unit/test_something.py::test_fn  # single test
```

Pytest markers: `unit`, `integration`, `contract`, `slow`, `ai`, `runtime`, `semantic`, `federation`, `connectors`.

**Build:**
```bash
make build              # runtime + SDK packages
make ui-build           # React UI → langbridge/ui/static
cd apps/runtime_ui_next && npm run dev   # UI dev server
```

**Docker:**
```bash
docker compose --profile host up --build runtime-host
```

**Runtime boundary check** (enforced in CI):
```bash
python scripts/check_runtime_boundary.py
```

## Architecture

Langbridge is a self-hostable agentic analytics runtime. The core package is `langbridge/`, with a React frontend in `apps/runtime_ui_next/` and a separate SDK distribution in `packages/sdk/`.

### Request flow

```
SDK Client / HTTP / CLI
  → LangbridgeClient (.local() or .for_runtime_host())
    → RuntimeHost (FastAPI, auth, ODBC endpoint)
      → RuntimeContext (workspace_id, actor_id, roles, request_id)
        → Services: dataset query, SQL, semantic query, sync, agent execution
          → Federation engine, connectors, AI orchestration
```

### Key modules

**`langbridge.runtime`** — the host and all server-side wiring
- `bootstrap/` — assembles `RuntimeHost` from YAML config
- `hosting/` — FastAPI app, auth modes (`none`/`static_token`/`jwt`), ODBC endpoint, background tasks
- `services/` — dataset, SQL, semantic, sync, agent execution services
- `persistence/` — SQLAlchemy models, Alembic migrations, UoW pattern, repositories
- `providers/` — metadata (datasets, connectors, semantic models), credentials, cache
- `context.py` — `RuntimeContext` carries workspace/actor identity through every operation

**`langbridge.federation`** — distributed query planning and execution
- `planner/` — logical → physical plan with pushdown optimization
- `executor/` — stage-based execution with artifact store (caching/offloading)
- `connectors/` — federation-level SQL, API, file, Parquet connectors
- `models/` — execution plans, SMQ (Semantic Modeling Query), virtual datasets

**`langbridge.semantic`** — semantic data modeling layer
- `model.py`, `unified_model.py` — contracts for tables, measures, dimensions, relationships
- `loader.py` — YAML/JSON semantic model loading and validation
- `graph_compiler.py` — compiles semantic queries to logical plans

**`langbridge.connectors`** — data source integrations
- `sql/` — Postgres, MySQL, Snowflake, BigQuery, Redshift, Databricks, SQLite
- `saas/` — Shopify, Stripe, Salesforce, HubSpot, Zendesk, Google Analytics
- `nosql/` — MongoDB; `vector/` — Pinecone, Faiss; `storage/` — DuckDB
- `base/` — connector interface, config schema, metadata, error handling

**`langbridge.ai`** — agent orchestration and LLM workflows
- `orchestration/` — PlannerAgent, MetaControllerAgent, FinalReviewAgent (multi-agent pipeline)
- `llm/` — Anthropic Claude and OpenAI abstractions, structured outputs
- `routing.py` — question profiling and agent routing
- `factory.py` — builds agent profiles from runtime config

**`langbridge.client`** — Python SDK
- `LangbridgeClient.local(config_path=...)` — in-process runtime
- `LangbridgeClient.for_runtime_host(base_url=..., token=...)` — HTTP client
- Sub-clients: `.datasets`, `.semantic`, `.sql`, `.sync`, `.agents`

**`langbridge.mcp`** — MCP server mounted when `features: mcp` is set

**`langbridge.ui`** — compiled React assets served when `features: ui` is set

### Identity and scoping

Every request is scoped to a `workspace_id`. `RuntimeContext` (see `langbridge/runtime/context.py`) carries workspace_id, actor_id, roles, and request_id and is threaded through all service calls. Auth is configured per-deployment in YAML (`auth.mode`).

### Connector extension

New connectors inherit from `langbridge.connectors.base`. Additional connector packages live in `langbridge-connectors/` and register via the plugin surface in `langbridge/plugins/`.

### Config

Runtime is configured via a YAML file passed to `langbridge serve --config`. See `examples/deployment/runtime_host/langbridge_config.yml` for a reference config. Document new config keys in `docs/deployment/self-hosted.md`.
