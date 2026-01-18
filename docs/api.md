# API Overview

Base path: `/api/v1`

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
