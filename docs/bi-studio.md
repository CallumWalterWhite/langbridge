# BI Studio

BI Studio is the lightweight dashboard builder. It reads semantic models via the meta endpoint and sends queries to the semantic query endpoint.

## Data flow
1) UI loads `/semantic-query/{id}/meta` to fetch the canonical model.
2) UI loads saved dashboards from `/bi-dashboard/{organization_id}`.
3) User configures widgets, per-widget filters, and global filters.
4) UI submits `/semantic-query/{id}/q` with global filters merged into every widget query.
5) Results render as tables or charts and dashboards can be saved/updated/deleted.

## UI entry points
- Page: `client/src/app/(app)/bi/page.tsx`
- Main studio: `client/src/app/(app)/bi/[organizationId]/page.tsx`
- API helpers: `client/src/orchestration/semanticQuery/*`
- Dashboard API helpers: `client/src/orchestration/dashboards/*`
- Charts: `recharts` (bar, line, pie)

## Adding features
- New chart type: extend `client/src/app/(app)/bi/_components/BiWidgetTile.tsx`.
- New query options: update the UI builder and `SemanticQueryPayload` types.
- New persisted dashboard fields: update `langbridge/packages/common/langbridge_common/contracts/dashboards.py`.
- New model fields: update `docs/semantic-model.md` and `semantic/loader.py`.
