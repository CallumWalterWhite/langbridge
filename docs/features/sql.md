# SQL Feature

Langbridge SQL is a first-class in-product SQL workbench for native SQL execution through the Worker execution plane.

## Product Scope

- UI-native SQL editor (`/sql/{organizationId}`).
- Connection selector and federated source builder.
- Parameterized SQL, explain, query history, saved queries.
- Result preview with server-enforced limits.
- Export controls and workspace policy enforcement.
- Optional AI assistance for SQL generation/fix/explain.

## Architecture

1. User writes SQL in UI (default T-SQL or connector dialect).
2. Control plane validates request and policy bounds.
3. SQL job is enqueued and executed by worker handler.
4. Worker applies safety checks and limit/timeout enforcement.
5. Results and artifacts are persisted and retrieved via SQL job APIs.

No direct execution occurs in UI or API process.

## API Surface

Base: `/api/v1/sql`

- `POST /execute`
- `POST /cancel`
- `GET /jobs/{sql_job_id}`
- `GET /jobs/{sql_job_id}/results`
- `GET /jobs/{sql_job_id}/results/download?format=csv|parquet`
- `GET /history`
- `POST /saved`
- `GET /saved`
- `GET /saved/{saved_query_id}`
- `PUT /saved/{saved_query_id}`
- `DELETE /saved/{saved_query_id}`
- `GET /policies`
- `PUT /policies`
- `POST /assist`

## Policy and Guardrails

- Read-only by default; DML requires explicit policy enablement.
- Enforced preview/export row caps.
- Enforced runtime and concurrency limits.
- Workspace schema/table allowlists.
- Result redaction rules where configured.
- Correlation IDs and job IDs exposed for supportability.

## Federated SQL Authoring

Federated mode maps source aliases to connectors and executes via worker federation pipeline.

Query pattern:

```sql
SELECT TOP 100
  a.id,
  b.id
FROM crm.public.accounts AS a
JOIN billing.public.accounts AS b
  ON a.id = b.id
ORDER BY a.id DESC;
```

Where `crm` and `billing` are source aliases configured in the SQL sidebar.
