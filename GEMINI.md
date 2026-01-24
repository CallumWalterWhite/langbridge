# Repository Guidelines

## Project Structure & Module Organization
Langbridge spans a FastAPI backend and a Next.js UI. Backend logic stays under `langbridge/` with routers in `langbridge/api`, connector/orchestrator flows in their domain folders, and shared DI utilities inside `config.py`, `ioc/`, `middleware/`, and `semantic/`. The UI follows the Next.js App Router at `client/src/app`, with shared components in `client/src/components` and workflow helpers in `client/src/orchestration`. Tests sit in `tests/` (api, connectors, orchestrator, unit) and module-scoped fixtures can live in `langbridge/tests`. Reference docs remain in `docs/`.

## Build, Test, and Development Commands
- `python -m venv .venv && ./.venv/Scripts/activate && pip install -r langbridge/requirements.txt` (or `source .venv/bin/activate`) bootstraps backend deps.
- `python langbridge/main.py` (or `fastapi run main.py`) starts the API via DI.
- `cd client && npm install && npm run dev` runs the Next.js dev server; `npm run build && npm run start` serves production output.
- `docker compose up --build` wires API, UI, Postgres, and Redis for full-stack verification.
- `pytest -q tests` runs backend suites; trim scope with paths like `pytest tests/orchestrator`.
- `cd client && npm run lint` must pass before committing UI changes.

## Coding Style & Naming Conventions
Follow 4-space indentation, full type hints, and FastAPI dependency-injection helpers. Keep backend modules domain-focused (`semantic/translators/*.py`, `connectors/shopify/*.py`). Functions stay snake_case, dynamically generated route IDs remain kebab-case via `custom_generate_unique_id`. In the client, build PascalCase components, camelCase hooks/utilities, and rely on Tailwind/PostCSS enforced through the shared ESLint config.

## Testing Guidelines
Name backend tests `test_<feature>.py`, reuse fixtures from `tests/conftest.py`, and cover both success/failure branches for orchestrators and connectors. Any API contract change should include expectation tests plus regenerated client types. UI changes must lint clean and add Playwright or React Testing Library coverage when behavior is stateful.

## Commit & Pull Request Guidelines
Write concise, present-tense commit subjects mirroring history (`change semantic translator to support dialect target`). Pull requests should describe motivation, link issues, attach UI screenshots/GIFs, and call out schema or config impacts so reviewers can double-check `docs/semantic-model.md` and `docs/api.md`.

## Security & Configuration Tips
Secrets load from `.env` via `langbridge/config.py`; never commit `.env*`, `.db`, or log files. Document new toggles in `docs/development.md`, prefer safe defaults, and coordinate with ops before altering agent hosts or OAuth credentials. When enabling Shopify, GitHub, or Google connectors, keep backend env vars and `client/.env.local` entries aligned to maintain redirect parity.