# Langbridge

Langbridge is a full-stack agent orchestration platform for building AI assistants
that can plan, call tools, and answer questions with data-backed context. It ships
with a FastAPI backend, a Next.js client, and an orchestrator that routes requests
across tools like SQL analysis, web search, deep research, and visualization.

## What it does
- Build and manage agent definitions (prompt contract, memory strategy, tools, output schema).
- Orchestrate multi-step workflows with a planner + supervisor loop.
- Run tool-backed agents: SQL analyst, web search, deep research, visualization.
- Store chat threads, messages, and tool-call logs.
- Provide a UI for LLM connections, agent setup, and chats.

## Architecture
- Backend: FastAPI + SQLAlchemy + dependency-injector (`langbridge/`).
- Orchestrator: planner + supervisor + agents (`langbridge/orchestrator/`).
- Frontend: Next.js app (`client/`).
- Storage: Postgres for data, Redis for caching/queues (via docker-compose).

## Quick start (Docker)
```bash
docker compose up --build
```

Then open:
- UI: `http://localhost:3000`
- API docs: `http://localhost:8000/docs`

## Local development (optional)
Backend:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r langbridge/requirements.txt
python langbridge/main.py
```

Frontend:
```bash
cd client
npm install
npm run dev
```

## Repo layout
- `langbridge/`: FastAPI app, orchestration logic, connectors, services, models.
- `client/`: Next.js UI.
- `proxy/`: database proxy container config.
- `tests/`: backend tests.
- `docker-compose.yml`: local dev stack (API, UI, Postgres, Redis).

## Getting started in the UI
1. Create an LLM connection.
2. Create an agent definition (tools, prompts, memory, output schema).
3. Start a chat thread and select your agent.
