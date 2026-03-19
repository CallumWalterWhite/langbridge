# Development

This page is a short index for runtime development.

## Development Docs

- Local development: `docs/development/local-dev.md`
- Worker development: `docs/development/worker-dev.md`
- Self-hosted runtime deployment: `docs/deployment/self-hosted.md`
- Hybrid runtime deployment: `docs/deployment/hybrid.md`

## Quick Commands

- Install runtime dependencies: `pip install -r requirements.txt`
- Run the worker: `python -m langbridge.apps.runtime_worker.main`
- Run unit tests: `pytest -q tests/unit`
- Start the local runtime stack: `docker compose up --build db redis worker`

## Notes

- SQL, semantic, dataset, and agent execution all run through the runtime worker.
- Federated execution is the primary structured execution path in the runtime.
