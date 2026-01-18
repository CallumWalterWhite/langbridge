# BI Studio

BI Studio is the lightweight dashboard builder. It reads semantic models via the meta endpoint and sends queries to the semantic query endpoint.

## Data flow
1) UI loads `/semantic-query/{id}/meta` to fetch the canonical model.
2) User selects dimensions, measures, segments, and filters.
3) UI submits `/semantic-query/{id}/q`.
4) Results render as a table and basic charts.

## UI entry points
- Page: `client/src/app/(app)/bi/page.tsx`
- API helpers: `client/src/orchestration/semanticQuery/*`
- Charts: `recharts` (bar, line, pie)

## Adding features
- New chart type: extend `ChartPreview` in `bi/page.tsx`.
- New query options: update the UI builder and `SemanticQueryPayload` types.
- New model fields: update `docs/semantic-model.md` and `semantic/loader.py`.
