# Custom Trino Image (Tenant-Aware JDBC)

This build replaces Trino JDBC connector jars with patched versions that route
connector connections through `TenantAwareConnectionFactory`.

## What It Patches

- `plugin/trino-base-jdbc`: adds `TenantAwareConnectionFactory`
- `plugin/trino-postgresql`: uses tenant-aware connection factory
- `plugin/trino-mysql`: uses tenant-aware connection factory
- `plugin/trino-sqlserver`: uses tenant-aware connection factory

Patch file:

- `langbridge/services/trino/custom/patches/0001-tenant-aware-jdbc-routing.patch`

## Build

Docker compose builds this image automatically for the `trino` service.

Manual build:

```bash
docker build \
  -f langbridge/services/trino/custom/Dockerfile \
  --build-arg TRINO_VERSION=455 \
  -t langbridge-trino-custom:455 \
  .
```

## Runtime Contract

- Catalog placeholders may be in `connection-url` and/or JDBC properties such as `connection-user`.
- MySQL connector requires URL without database/catalog; this repo carries tenant/source in `connection-user`.
- Callers must pass `X-Trino-Extra-Credential: tenant=<id>`.
- The gateway already forwards extra credentials on query execution.
