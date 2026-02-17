# Multi-Tenant Trino JDBC Routing

This module contains a tenant-aware JDBC `ConnectionFactory` implementation for Trino JDBC connectors.

## Purpose
- Read tenant/source identifiers from Trino extra credentials.
- Materialize connector JDBC URLs (for example `.../{tenant}`) before opening each JDBC connection.
- Ensure all connector connections sent to the Langbridge gateway include tenant context.

## Routing Contract
- Required extra credential: `tenant`
- Optional extra credential: `source`
- Placeholders can appear in JDBC URL and/or JDBC properties.
- MySQL connector note: JDBC URL must not include database/catalog.

Examples:
- `jdbc:postgresql://gateway-proxy:55432/{tenant}`
- `jdbc:mysql://gateway-proxy:53306` with `connection-user=tenant:{tenant};user:trino`
- `jdbc:sqlserver://gateway-proxy:51433;databaseName={tenant}`

## Integration Notes
This repo includes a custom Trino Docker build pipeline that applies the JDBC
integration patch automatically:

- Docker build: `langbridge/services/trino/custom/Dockerfile`
- Patch: `langbridge/services/trino/custom/patches/0001-tenant-aware-jdbc-routing.patch`

The patch wires `TenantAwareConnectionFactory` into PostgreSQL, MySQL, and
SQL Server JDBC connector modules.

Runtime requirements:
1. Configure catalog placeholders in `connection-url` and/or `connection-user`.
2. Ensure clients pass `X-Trino-Extra-Credential: tenant=<id>` (and optional `source=<id>`).
