# Repository Guidelines

## Project Structure & Module Organization
Langbridge pairs a FastAPI backend with a Next.js UI. Backend apps live under `langbridge/apps` (`api`, `worker`, `gateway`), while shared Python packages live under `langbridge/packages` (`common`, `messaging`, `orchestrator`, `connectors`, `semantic`). API models and data access live in `langbridge/apps/api/langbridge_api/db` and repositories; shared DB models go in `langbridge/packages/common/langbridge_common/db`. Frontend source sits in `client/src/app`, with shared UI in `client/src/components` and workflow helpers in `client/src/orchestration`. Core tests are grouped in `tests/` (api, connectors, orchestrator, unit), while module-specific fixtures may live in `langbridge/tests`. Docs and semantic/API references stay in `docs/`.

## Build, Test, and Development Commands
- `python -m venv .venv && ./.venv/Scripts/activate && pip install -r langbridge/requirements.txt` installs backend deps (use `source .venv/bin/activate` on macOS/Linux).
- `python langbridge/main.py` (shim) or `uvicorn langbridge.apps.api.langbridge_api.main:app` starts the API via dependency injection.
- `python -m langbridge.apps.worker.langbridge_worker.main` runs the Redis-backed worker.
- `cd client && npm install && npm run dev` runs the Next.js dev server; `npm run build && npm run start` serves the production bundle.
- `docker compose up --build` launches API, UI, Postgres, and Redis for integrated verification.
- `pytest -q tests` executes backend suites; limit scope with subpaths such as `pytest tests/orchestrator`.
- `alembic revision --autogenerate -m "describe change"` and `alembic upgrade head` manage schema migrations.
- `cd client && npm run lint` must be clean before opening a PR.

## Coding Style & Naming Conventions
Use 4-space indentation, type hints, and FastAPI dependency-injection patterns. Keep backend modules cohesive by domain (`semantic/translators/*.py`, `connectors/shopify/*.py`). Functions are snake_case, generated route IDs remain kebab-case via `custom_generate_unique_id`. On the frontend, components are PascalCase, hooks/utilities are camelCase, and Tailwind/PostCSS formatting is enforced by the shared ESLint config.

## Testing Guidelines
Create pytest modules as `test_<feature>.py`, reuse fixtures from `tests/conftest.py`, and cover positive plus failure flows for orchestrators/connectors. Pair any API contract change with expectation tests and regenerate client types. UI changes should keep `npm run lint` clean and add Playwright or React Testing Library coverage when stateful behavior is introduced.

## Commit & Pull Request Guidelines
Write present-tense commit subjects similar to `change semantic translator to support dialect target`. Pull requests should explain motivation, link the tracking issue, attach UI screenshots or GIFs for visible changes, and flag migrations, semantic-model edits, or config impacts so reviewers can verify `docs/semantic-model.md` and `docs/api.md`.

## Security & Configuration Tips
Settings flow from `.env` via `langbridge/config.py`; never commit secrets, `.env*`, `.db`, or log files (already Git-ignored). Document new configuration knobs in `docs/development.md`, choose safe defaults, and coordinate with ops when changing agent hosts or OAuth credentials. Enable Shopify/GitHub/Google integrations only after syncing backend env vars with `client/.env.local` so redirect URIs stay aligned.
