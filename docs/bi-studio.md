# BI Studio

BI Studio is a lightweight semantic dashboard surface inside Langbridge.

It is intentionally not the primary product surface. Langbridge's core product direction is agentic analytics infrastructure (semantic + SQL + federated execution + agents).

## Data Flow

1. UI loads semantic metadata from `/semantic-query/{id}/meta`.
2. UI loads/saves dashboards via `/bi-dashboard/*`.
3. Widget queries are dispatched via semantic query APIs.
4. Worker runtime executes underlying jobs and returns results.

## UI Entry Points

- `client/src/app/(app)/bi/page.tsx`
- `client/src/app/(app)/bi/[organizationId]/page.tsx`
- `client/src/orchestration/semanticQuery/*`
- `client/src/orchestration/dashboards/*`

## Notes

- BI Studio complements, but does not replace, SQL Workbench and agent workflows.
- Federated execution capabilities are shared with semantic and SQL workloads.
