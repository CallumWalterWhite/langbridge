# Semantic Model Guide

The canonical semantic model is defined in `langbridge/semantic/model.py`. All runtime paths must use this schema.

## Canonical fields
- `version`: string
- `name`: optional string
- `connector`: optional string
- `dialect`: optional string
- `description`: optional string
- `tags`: optional list of strings
- `tables`: map of table key to `Table`
- `relationships`: optional list of `Relationship`
- `metrics`: optional map of metric key to `Metric`

### Table
- `schema`: database schema name
- `name`: physical table name
- `description`: optional
- `synonyms`: optional list
- `dimensions`: optional list of `Dimension`
- `measures`: optional list of `Measure`
- `filters`: optional map of filter name to `TableFilter`

### Dimension
- `name`, `type`, `primary_key`
- `description`, `alias`, `synonyms`
- `vectorized`: boolean
- `vector_reference`: string reference for managed vector stores
- `vector_index`: metadata payload used by semantic search

### Measure
- `name`, `type`
- `aggregation`: optional
- `description`, `synonyms`

### Relationship
- `name`
- `from_`: table key
- `to`: table key
- `type`: one_to_many, many_to_one, one_to_one, many_to_many, inner, left, right, full
- `join_on`: join condition string

### Metric
- `expression`: SQL expression referencing table keys
- `description`: optional

## Legacy payload support
`semantic/loader.py` accepts:
- Legacy entities-first payloads (`entities`, `joins`, `dimensions`).
- Unified payloads (`semantic_models` list).

Both are normalized into the canonical table-based model.

## Example YAML
```yaml
version: "1.0"
name: sales_semantic
connector: warehouse
tables:
  sales:
    schema: public
    name: sales
    dimensions:
      - name: order_id
        type: string
        primary_key: true
      - name: customer_id
        type: string
    measures:
      - name: revenue
        type: decimal
        aggregation: sum
  customers:
    schema: public
    name: customers
    dimensions:
      - name: id
        type: string
        primary_key: true
relationships:
  - name: sales_to_customers
    from_: sales
    to: customers
    type: many_to_one
    join_on: sales.customer_id = customers.id
metrics:
  revenue_per_order:
    expression: sales.revenue / sales.order_id
```

## Rules for changes
- Do not create a second Pydantic semantic model.
- Parse all inputs through `semantic/loader.py`.
- Update this doc if fields or semantics change.
