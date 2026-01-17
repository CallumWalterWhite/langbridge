# Architecture Overview

This project is split into a FastAPI backend and a Next.js frontend. The key goal is to build semantic models that power both agent tooling and lightweight BI queries.

## Backend (FastAPI)
- Entry point: `langbridge/main.py`
- Routers: `langbridge/api/v1/`
- Services: `langbridge/services/`
- Models: `langbridge/models/`
- Semantic system: `langbridge/semantic/`
- Orchestrator: `langbridge/orchestrator/`

Core flows:
1) Semantic model creation
   - `SemanticModelService.create_model` stores canonical YAML and JSON.
   - Legacy payloads are normalized via `semantic/loader.py`.
2) Semantic query execution
   - `SemanticQueryService.query_request` loads canonical model, translates semantic query to SQL, and runs it through a connector.
3) Orchestrated SQL analyst
   - `SqlAnalystTool` consumes the canonical `SemanticModel` and generates SQL via the LLM.

## Frontend (Next.js)
- App routes: `client/src/app/(app)/...`
- API helpers: `client/src/orchestration/`
- Shared UI: `client/src/components/ui/`

Core screens:
- Semantic model builder: `client/src/app/(app)/semantic-model/create/page.tsx`
- Unified semantic model builder: `client/src/app/(app)/semantic-model/unified/page.tsx`
- BI Studio: `client/src/app/(app)/bi/page.tsx`

## Data flow
1) User builds or uploads a semantic model.
2) Backend normalizes to canonical schema and persists YAML.
3) BI Studio calls `/semantic-query/{id}/meta` to fetch the model.
4) User builds a query and calls `/semantic-query/{id}/q`.
5) Results render as tables or charts.
