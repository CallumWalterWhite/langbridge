# Development

This page now points to the split development docs.

## Development Docs

- Local development: `docs/development/local-dev.md`
- Worker development: `docs/development/worker-dev.md`
- Hosted deployment: `docs/deployment/hosted.md`
- Hybrid deployment: `docs/deployment/hybrid.md`
- Self-hosted deployment: `docs/deployment/self-hosted.md`

## Quick Commands

- API: `python langbridge/main.py`
- Worker: `python -m langbridge.apps.worker.langbridge_worker.main`
- UI: `cd client && npm install && npm run dev`
- Unit tests: `pytest -q tests/unit`
- Frontend lint: `cd client && npm run lint`

## Notes

- SQL and semantic execution run through Worker + Federated Query Engine.
- Trino/SQL gateway runtime is deprecated and not required for active development direction.
