# Development

This section documents development of the runtime repository.

Use `langbridge/` for runtime work. Use `../langbridge-cloud` when the change is
about hosted control-plane APIs, web surfaces, or hosted orchestration.

## Development Docs

- `docs/development/local-dev.md`
- `docs/development/worker-dev.md`
- `docs/deployment/self-hosted.md`
- `docs/deployment/hybrid.md`

## Common Commands

Install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements/dev.txt
pip install -e .
```

Run the runtime host:

```bash
langbridge serve --config examples/runtime_host/langbridge_config.yml --host 127.0.0.1 --port 8000
```

Build the runtime-owned UI bundle:

```bash
cd apps/runtime_ui
npm install
npm run build
```

Run the queued worker:

```bash
python -m apps.runtime_worker.main
```

Run tests:

```bash
pytest -q tests
```

Bring up local containers:

```bash
docker compose up --build
```
