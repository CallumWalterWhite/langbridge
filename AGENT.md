# Agent Implementation Guide

This guide is the primary reference for Codex changes in LangBridge. It is concise by design. For deeper context, see the docs in `docs/`.

## Repo map
- Backend API: `langbridge/` (FastAPI + SQLAlchemy + DI container).
- Frontend app: `client/` (Next.js App Router).
- Tests: `tests/` (backend).
- Docs: `docs/` (architecture, API, semantic model, BI Studio).

## Build and run
- Docker (full stack): `docker compose up --build`
- Backend local: `python langbridge/main.py` (after venv + requirements)
- Frontend local: `cd client && npm install && npm run dev`

## Backend conventions
- Routers live in `langbridge/api/v1/` and use DI via `Depends(Provide[Container.<provider>])`.
- Service errors use `BusinessValidationError`, mapped to HTTP 400/404 in routes.
- Repositories return DB entities; services map to response models in `langbridge/models/`.

## Canonical semantic model (single Pydantic model)
- Canonical schema lives in `langbridge/semantic/model.py`.
- Always parse incoming YAML/JSON using `langbridge/semantic/loader.py`:
  - Accepts legacy payloads (`entities`, `joins`, `dimensions`) and unified payloads (`semantic_models`).
  - Normalizes into table-based `SemanticModel` so runtime logic stays single-model.
- Vectorization writes to `Dimension.vector_index` and `Dimension.vector_reference`.
- Do not reintroduce separate Pydantic models for SQL analyst vs semantic query.

## Semantic query API
- Run query: `POST /api/v1/semantic-query/{semantic_model_id}/q`
  - Body: `SemanticQueryRequest` in `langbridge/models/semantic/semantic_query.py`.
- Meta endpoint: `GET /api/v1/semantic-query/{semantic_model_id}/meta?organization_id=...`
  - Returns canonical semantic model JSON for UI builders.

## SQL analyst tool
- Tool consumes `semantic.model.SemanticModel` (table-based).
- Prompt rendering uses tables, relationships, measures, dimensions, and metrics.
- Vector search uses `Dimension.vector_index` metadata.

## Frontend conventions
- Routes live in `client/src/app/(app)/...`.
- Data access uses React Query with stable keys.
- API wrappers live in `client/src/orchestration/<feature>` with types in `types.ts`.
- Use `useWorkspaceScope` for org/project scoping.
- BI Studio UI: `client/src/app/(app)/bi/page.tsx`.

## Change checklist
- Keep API models and client types in sync.
- If changing semantic model fields, update `semantic/loader.py` and docs.
- Update `docs/` when adding endpoints or UI flows.
