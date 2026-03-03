# Semantic Model Guide

The canonical semantic model is defined in:
- `langbridge/packages/semantic/langbridge_semantic/model.py`

All runtime paths should normalize incoming payloads to this schema.

## Canonical Fields

- `version`: string
- `name`: optional string
- `connector`: optional string
- `dialect`: optional string
- `description`: optional string
- `tags`: optional list of strings
- `tables`: map of table key to `Table`
- `relationships`: optional list of `Relationship`
- `metrics`: optional map of metric key to `Metric`

## Table

- `dataset_id`: optional dataset reference (preferred for new models)
- `schema`: database schema name
- `name`: physical table name
- `description`: optional
- `synonyms`: optional list
- `dimensions`: optional list of `Dimension`
- `measures`: optional list of `Measure`
- `filters`: optional map of filter name to `TableFilter`

Compatibility rules:
- If `dataset_id` is present, execution resolves table bindings from the referenced dataset.
- If `dataset_id` is absent, execution uses legacy physical table binding (`schema` + `name`).

## Dimension

- `name`, `type`, `primary_key`
- `description`, `alias`, `synonyms`
- `vectorized`: boolean
- `vector_reference`: string reference for managed vector stores
- `vector_index`: metadata payload used by semantic search

## Measure

- `name`, `type`
- `aggregation`: optional
- `description`, `synonyms`

## Relationship

- `name`
- `from_`: table key
- `to`: table key
- `type`: one_to_many, many_to_one, one_to_one, many_to_many, inner, left, right, full
- `join_on`: join condition string

## Metric

- `expression`: SQL expression referencing table keys
- `description`: optional

## Legacy Payload Support

Loader:
- `langbridge/packages/semantic/langbridge_semantic/loader.py`

Supported input styles include legacy and unified payload shapes, both normalized into canonical model.

## Change Rules

- Do not create parallel semantic schemas.
- Parse all semantic payloads through the loader.
- Update this document when semantic contract fields or meaning change.
