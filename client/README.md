# Langbridge UI

This frontend is the Langbridge Control Plane UI built with Next.js.

## Core Product Surfaces

- SQL Workbench (`/sql`)
- Semantic Models (`/semantic-model`)
- BI Studio (`/bi`)
- Agents (`/agents`)
- Data Connections (`/datasources`)

## Development

```bash
npm install
npm run dev
```

Open `http://localhost:3000`.

Set backend URL in `.env.local`:

```bash
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
```

## Notes

- SQL execution is API + Worker mediated; no direct browser-to-database path.
- Federated and semantic workloads share backend execution infrastructure.
