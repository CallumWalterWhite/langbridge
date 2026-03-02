# Deprecations and Migration

## Migration Note

**Trino removed in favor of built-in Federated Query Engine.**

Langbridge's target architecture no longer depends on:
- Trino as external federated query runtime.
- SQL gateway as an external SQL data plane.

The built-in federated planner and execution engine (Worker + `packages/federation`) is now the primary structured engine.

## Deprecated Modules (Safe to Remove in Next Major)

The following modules are deprecated and should be removed in a staged cleanup:

- `langbridge/apps/gateway/**`
- `langbridge/services/trino/**`
- `langbridge/packages/connectors/langbridge_connectors/api/_trino/**`
- `langbridge/Dockerfile.gateway`
- `langbridge/apps/gateway/langbridge_gateway/Dockerfile`

Legacy operational wiring also pending removal:

- `docker-compose.yml` services: `gateway`, `gateway-proxy`, `trino`
- `docker-compose.sales.yml` services: `gateway`, `gateway-proxy`, `trino`
- CI docker matrix entry for `langbridge/Dockerfile.gateway`
- Legacy env variables:
  - `TRINO_*`
  - `UNIFIED_TRINO_*`

## Backward Compatibility Notes

- Legacy modules may still exist in source and compose files for transitional compatibility.
- They are not required for SQL or semantic execution in the current architecture direction.
- New implementation work should target control-plane dispatch + worker execution + federation package only.
