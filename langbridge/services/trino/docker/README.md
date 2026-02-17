# Trino Compose Assets

This folder contains the Trino coordinator and catalog configuration mounted by:

- `docker-compose.yml`
- `docker-compose.sales.yml`

Both compose stacks build a custom Trino image from:

- `langbridge/services/trino/custom/Dockerfile`

## Files

- `config.properties`: single-node coordinator settings.
- `catalog-gateway/*.properties`: tenant-aware Trino catalogs that route through
  the Langbridge protocol proxy and require runtime tenant replacement:
  - `postgres.properties`
  - `mysql.properties`
  - `sqlserver.properties`

## Runtime contract

- Tenant/source placeholders can be used in JDBC URL and JDBC properties.
  The patched Trino multi-tenant connection factory materializes both.
- MySQL connector requires URL without database/catalog. For MySQL in this repo,
  tenant/source are carried in `connection-user`.
- Trino must receive `X-Trino-Extra-Credential: tenant=<id>` for routed JDBC
  connections.
- The gateway proxy service listens on:
  - Postgres: `gateway-proxy:55432`
  - MySQL: `gateway-proxy:53306`
  - SQL Server: `gateway-proxy:51433`

## Verification

After `docker compose up --build`, verify Trino is reachable:

```bash
curl http://localhost:8080/v1/info
```
