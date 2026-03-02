# Insomnia Collection

`langbridge_collection.yml` contains the generated Langbridge REST API request set from `langbridge/apps/api/langbridge_api/routers/v1`.

Regenerate:

```bash
python scripts/generate_api_collections.py
```

## Import

1. Open Insomnia.
2. Go to `Application -> Preferences -> Data -> Import Data`.
3. Select `docs/insomnia/langbridge_collection.yml`.

## Base Environment

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
- `SCHEMA_NAME`
- `TABLE_NAME`

Most endpoints require auth. Set `DEFAULT_HEADERS.Authorization` to `Bearer <token>`.

## Notes

- SQL workbench lifecycle endpoints are under `/api/v1/sql/*`.
- Customer runtime transport endpoints are under `/api/v1/edge/tasks/*`.
