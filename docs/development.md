# Development Notes

This doc is aimed at quick onboarding for Codex and contributors.

## Backend
- Create venv and install requirements:
  - `python -m venv .venv`
  - `.\.venv\Scripts\activate` (Windows)
  - `pip install -r langbridge/requirements.txt`
- Run API:
  - `python langbridge/main.py`
- Internal service auth:
  - Set `SERVICE_USER_SECRET` in `.env` to enable internal service calls.
  - Send `x-langbridge-service-token: <SERVICE_USER_SECRET>` to bypass cookie auth.
  - Internal API client is available via DI (`InternalApiClient`) for self-calls with the token.

## Frontend
- `cd client`
- `npm install`
- `npm run dev`

## Testing and linting
- Backend tests (if present): `pytest`
- API E2E automation: `pytest -q tests/e2e/test_api_e2e.py`
  - The E2E test boots the API with a temporary SQLite DB and exercises auth -> organization -> project -> thread endpoints.
  - If required backend dependencies are missing, the test is skipped with an actionable message.
- Frontend lint: `cd client && npm run lint`

## Hybrid runtime (control plane + customer runtime)
- Set API runtime token settings:
  - `EDGE_RUNTIME_JWT_SECRET=<strong-random-secret>`
  - `DEFAULT_EXECUTION_MODE=hosted` (or `customer_runtime` for a tenant when enabled through environment settings)
- Create a one-time registration token from the API:
  - `POST /api/v1/runtimes/{organization_id}/tokens`
- Start local stack with optional customer runtime profile:
  - `docker compose --profile customer-runtime up --build`
- In customer environments, use `docker-compose.customer-runtime.yml` and set:
  - `EDGE_API_BASE_URL` to the control-plane URL
  - `EDGE_REGISTRATION_TOKEN` to the one-time token
- Customer runtime transport uses outbound HTTPS long-polling:
  - `POST /api/v1/edge/tasks/pull`
  - `POST /api/v1/edge/tasks/ack`
  - `POST /api/v1/edge/tasks/result`
  - `POST /api/v1/edge/tasks/fail`

## Federated query engine (Trino-free data plane path)
- Core docs: `docs/federated-query-engine.md`
- Worker tool entrypoint:
  - `langbridge/apps/worker/langbridge_worker/tools/federated_query_tool.py`
  - method: `execute_federated_query(query_payload)`
- Runtime knobs (env):
  - `FEDERATION_ARTIFACT_DIR` (default `.cache/federation`)
  - `FEDERATION_BROADCAST_THRESHOLD_BYTES` (default `67108864`)
  - `FEDERATION_PARTITION_COUNT` (default `8`)
  - `FEDERATION_STAGE_MAX_RETRIES` (default `2`)
  - `FEDERATION_STAGE_PARALLELISM` (default `4`)
- Optional local source profile for federation testing:
  - `docker compose --profile federation-sources up federation-db-a federation-db-b`

## Change safety checklist
- Keep API models and client types aligned.
- When modifying semantic models, update `semantic/loader.py` and `docs/semantic-model.md`.
- Add or update API docs in `docs/api.md` for new endpoints.
