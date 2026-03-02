# API Overview

Base path: `/api/v1`

For complete endpoint inventories, use:
- `docs/insomnia/langbridge_collection.yml`
- `docs/postman/langbridge_collection.json`

Regenerate collections with:

```bash
python scripts/generate_api_collections.py
```

## Architecture Note

API is Control Plane only. It validates requests, applies policy, persists metadata, and dispatches execution work to Worker runtime.

Heavy query execution is not performed in API process.

## SQL APIs

Base: `/sql`

- `POST /sql/execute`
- `POST /sql/cancel`
- `GET /sql/jobs/{sql_job_id}`
- `GET /sql/jobs/{sql_job_id}/results`
- `GET /sql/jobs/{sql_job_id}/results/download?format=csv|parquet`
- `GET /sql/history?workspace_id=...&scope=user|workspace`
- `POST /sql/saved`
- `GET /sql/saved?workspace_id=...`
- `GET /sql/saved/{saved_query_id}?workspace_id=...`
- `PUT /sql/saved/{saved_query_id}`
- `DELETE /sql/saved/{saved_query_id}?workspace_id=...`
- `GET /sql/policies?workspace_id=...`
- `PUT /sql/policies`
- `POST /sql/assist`

## Semantic Model APIs

- `GET /semantic-model?organization_id=...&project_id=...`
- `POST /semantic-model`
- `GET /semantic-model/{model_id}?organization_id=...`
- `GET /semantic-model/{model_id}/yaml?organization_id=...`
- `DELETE /semantic-model/{model_id}?organization_id=...`
- `GET /semantic-model/generate/yaml?connector_id=...`

## Semantic Query APIs

- `POST /semantic-query/{semantic_model_id}/q`
- `GET /semantic-query/{semantic_model_id}/meta?organization_id=...`

Semantic query jobs execute through Worker + federated engine path.

## BI Dashboard APIs

- `GET /bi-dashboard/{organization_id}?project_id=...`
- `POST /bi-dashboard/{organization_id}`
- `GET /bi-dashboard/{organization_id}/{dashboard_id}`
- `PUT /bi-dashboard/{organization_id}/{dashboard_id}`
- `DELETE /bi-dashboard/{organization_id}/{dashboard_id}`

## Runtime Registry APIs

- `POST /runtimes/register`
- `POST /runtimes/heartbeat`
- `POST /runtimes/capabilities`
- `POST /runtimes/{organization_id}/tokens`
- `GET /runtimes/{organization_id}/instances`

## Edge Task Transport APIs (Customer Runtime)

- `POST /edge/tasks/pull`
- `POST /edge/tasks/ack`
- `POST /edge/tasks/result`
- `POST /edge/tasks/fail`

These endpoints provide secure task transport between control plane and customer runtime workers.
