# Runtime UI

This app is the source for the runtime-owned UI shell.

## Model

- Source code lives in `apps/runtime_ui`
- Production assets build into `langbridge/ui/static`
- The Python runtime host serves the built output from `langbridge.ui`

## Commands

Install dependencies:

```bash
npm install
```

Run the Vite dev server against a local runtime host:

```bash
langbridge serve --config examples/runtime_host/langbridge_config.yml --features ui
cd apps/runtime_ui
npm run dev
```

By default, Vite proxies `/api/*` to `http://127.0.0.1:8000`.

Build the production assets into the Python package:

```bash
cd apps/runtime_ui
npm run build
```
