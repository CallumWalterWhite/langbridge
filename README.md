# Langbridge

Langbridge is an orchestration platform for agents that coordinate real data sources,
run tool-backed workflows, and expose a shared UI for models, semantic data, and BI.

## Getting going
- API (FastAPI + DI + SQLAlchemy): `uvicorn langbridge.apps.api.langbridge_api.main:app --reload`.
- Worker (async execution): `python -m langbridge.apps.worker.langbridge_worker.main`.
- Publish a test message: `python -m langbridge.apps.worker.langbridge_worker.publish_test_message`.
- Gateway (SQL via Trino): `uvicorn langbridge.apps.gateway.langbridge_gateway.main:app --reload --port 8001`.
- Frontend (Next.js app): `cd client && npm install && npm run dev`.
- Docker: `docker compose up --build` and visit `http://localhost:3000` for the UI,
  `http://localhost:8000/docs` for the API, and `http://localhost:8001/health` for the gateway.

## Repo structure
- `langbridge/apps/api`: control plane (REST API, auth/tenancy, CRUD, job submission).
- `langbridge/apps/worker`: async execution plane (agents, scheduled jobs, connectors).
- `langbridge/apps/gateway`: SQL gateway/proxy (Trino HTTP client + tenant context).
- `langbridge/packages`: shared packages (common, messaging, semantic, orchestrator, connectors).
- `langbridge/services/trino/plugins`: stub Trino plugin workspace.
- `client/`: Next.js App Router experience.
- `tests/`: backend tests.
- `docker-compose.yml`: brings up the full stack (API, Worker, Gateway, UI, Postgres, Redis, etc.).

## Gateway notes
- The gateway accepts `POST /v1/query` with `{sql, tenant_id, source_id?, session?}`.
- Extra credentials are sent to Trino using `X-Trino-Extra-Credential: key=value` headers.
- Trino plugin folders are stubs only (no code yet). See `langbridge/services/trino/plugins`.

## Messaging notes
- Messaging uses Redis Streams with consumer groups and a dead-letter stream.
- Test publish endpoint: `POST /api/v1/messages/test` with JSON `{ "message_type": "test", "payload": {"message": "hello"} }`.
