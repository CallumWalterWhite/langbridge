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
- Frontend lint: `cd client && npm run lint`

## Change safety checklist
- Keep API models and client types aligned.
- When modifying semantic models, update `semantic/loader.py` and `docs/semantic-model.md`.
- Add or update API docs in `docs/api.md` for new endpoints.
