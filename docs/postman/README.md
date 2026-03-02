# Postman Collection

`langbridge_collection.json` contains the generated Langbridge REST API request set from `langbridge/apps/api/langbridge_api/routers/v1`.

Regenerate:

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
- `SCHEMA_NAME`
- `TABLE_NAME`

## Notes

- SQL APIs are included under `/api/v1/sql/*`.
- Runtime registration and edge task transport APIs are included under `/api/v1/runtimes/*` and `/api/v1/edge/tasks/*`.
