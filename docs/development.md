# Development Notes

This doc is aimed at quick onboarding for Codex and contributors.

## Backend
- Create venv and install requirements:
  - `python -m venv .venv`
  - `.\.venv\Scripts\activate` (Windows)
  - `pip install -r langbridge/requirements.txt`
- Run API:
  - `python langbridge/main.py`

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
