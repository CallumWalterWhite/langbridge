# Insomnia Collection

`langbridge_collection.yml` contains the full Langbridge REST API request set generated from `langbridge/apps/api/langbridge_api/routers/v1`.
Regenerate it with `python scripts/generate_api_collections.py`.

## Import
1. Open Insomnia.
2. Go to `Application` -> `Preferences` -> `Data` -> `Import Data`.
3. Select `docs/insomnia/langbridge_collection.yml`.

## Base Environment
Set these variables before running requests:
- `BASE_URL` (default `http://localhost:8000/`)
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

Most endpoints require auth. Set `DEFAULT_HEADERS.Authorization` to `Bearer <token>`.
