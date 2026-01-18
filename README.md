# Langbridge

Langbridge is an orchestration platform for agents that coordinate real data sources,
run tool-backed workflows, and expose a shared UI for models, semantic data, and BI.

## Getting going
- Backend (FastAPI + DI + SQLAlchemy): install deps then `cd langbridge && fastapi run main.py`.
- Frontend (Next.js app): `cd client && npm install && npm run dev`.
- Docker: `docker compose up --build` and visit `http://localhost:3000` for the UI,
  `http://localhost:8000/docs` for the API.

## Repo structure
- `langbridge/`: FastAPI services, orchestrator, semantic model handling.
- `client/`: Next.js App Router experience.
- `tests/`: backend tests.
- `docker-compose.yml`: brings up the full stack (API, UI, Postgres, Redis, etc.).
