# API Overview

Base path: `/api/v1`

For the complete and current endpoint inventory, use:
- `docs/insomnia/langbridge_collection.yml`
- `docs/postman/langbridge_collection.json`

Regenerate both from router source with `python scripts/generate_api_collections.py`.
This page is a partial overview.

## Semantic models
- `GET /semantic-model?organization_id=...&project_id=...`
  - List semantic models in scope.
- `POST /semantic-model`
  - Create a model. Body: `SemanticModelCreateRequest`.
- `GET /semantic-model/{model_id}?organization_id=...`
  - Fetch one model.
- `GET /semantic-model/{model_id}/yaml?organization_id=...`
  - Fetch YAML definition.
- `DELETE /semantic-model/{model_id}?organization_id=...`
  - Delete model.
- `GET /semantic-model/generate/yaml?connector_id=...`
  - Auto-generate a model from a connector.

## Semantic query
- `POST /semantic-query/{semantic_model_id}/q`
  - Body: `SemanticQueryRequest`
  - Returns: `SemanticQueryResponse`
- `GET /semantic-query/{semantic_model_id}/meta?organization_id=...`
  - Returns: `SemanticQueryMetaResponse` including `semantic_model`.

## BI dashboards
- `GET /bi-dashboard/{organization_id}?project_id=...`
  - List saved dashboards for an organization, optionally scoped to a project.
- `POST /bi-dashboard/{organization_id}`
  - Create a dashboard. Body: `DashboardCreateRequest`.
- `GET /bi-dashboard/{organization_id}/{dashboard_id}`
  - Fetch one saved dashboard.
- `PUT /bi-dashboard/{organization_id}/{dashboard_id}`
  - Update dashboard metadata, semantic model, global filters, and widgets.
- `DELETE /bi-dashboard/{organization_id}/{dashboard_id}`
  - Delete a saved dashboard.

## Runtime registry (customer-runtime)
- `POST /runtimes/register`
  - Exchange one-time registration token for an EP runtime identity and short-lived access token.
- `POST /runtimes/heartbeat`
  - Refresh runtime liveness and rotate access token.
- `POST /runtimes/capabilities`
  - Update runtime tags/capabilities for task routing.
- `POST /runtimes/{organization_id}/tokens`
  - Provision one-time registration tokens (authenticated org users).
- `GET /runtimes/{organization_id}/instances`
  - List runtime instances registered for an organization.

## Edge task gateway
- `POST /edge/tasks/pull`
  - Long-poll for leased tasks (at-least-once delivery with visibility timeout).
- `POST /edge/tasks/ack`
  - Acknowledge successful task processing.
- `POST /edge/tasks/result`
  - Submit worker events/results with idempotency key (`request_id`).
- `POST /edge/tasks/fail`
  - Negative-ack a task and trigger retry/backoff/dead-letter behavior.

## Example: meta
```http
GET /api/v1/semantic-query/00000000-0000-0000-0000-000000000000/meta?organization_id=00000000-0000-0000-0000-000000000000
```

## Example: semantic query
```json
{
  "organizationId": "00000000-0000-0000-0000-000000000000",
  "projectId": null,
  "semanticModelId": "00000000-0000-0000-0000-000000000000",
  "query": {
    "measures": ["sales.revenue"],
    "dimensions": ["sales.customer_id"],
    "filters": [
      { "member": "sales.customer_id", "operator": "equals", "values": ["123"] }
    ],
    "limit": 200
  }
}
```

## Example: dashboard create
```json
{
  "projectId": "00000000-0000-0000-0000-000000000000",
  "semanticModelId": "00000000-0000-0000-0000-000000000000",
  "name": "Revenue command center",
  "description": "Executive revenue dashboard",
  "globalFilters": [
    { "id": "gf-1", "member": "orders.region", "operator": "equals", "values": "US" }
  ],
  "widgets": [
    {
      "id": "w-1",
      "title": "Revenue by month",
      "type": "line",
      "size": "wide",
      "measures": ["orders.revenue"],
      "dimensions": ["orders.order_date"],
      "filters": [],
      "orderBys": [],
      "limit": 500,
      "timeDimension": "orders.order_date",
      "timeGrain": "month",
      "timeRangePreset": "last_30_days",
      "chartX": "orders.order_date",
      "chartY": "orders.revenue"
    }
  ]
}
```
