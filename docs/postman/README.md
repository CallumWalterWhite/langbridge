# Postman Collection

`langbridge_collection.json` contains the full Langbridge REST API request set generated from `langbridge/apps/api/langbridge_api/routers/v1`.

Regenerate it with:

```bash
python scripts/generate_api_collections.py
```

## Import
1. Open Postman.
2. Click `Import`.
3. Select `docs/postman/langbridge_collection.json`.

## Collection Variables
- `BASE_URL` (default `http://localhost:8000`)
- `TOKEN`
- `ORGANIZATION_ID`
- `PROJECT_ID`
- `CONNECTOR_ID`
- `MODEL_ID`
- `THREAD_ID`
- `AGENT_ID`
- `CONNECTION_ID`
- `DASHBOARD_ID`
- `JOB_ID`
- `CONNECTOR_TYPE`
- `PROVIDER`
- `SETTING_KEY`
- `SCHEMA_NAME`
- `TABLE_NAME`
