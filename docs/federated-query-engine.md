# Federated Query Engine (Worker Data Plane)

## Language choice (v1)
Langbridge v1 federation is implemented in **Python** to minimize integration friction with the existing Worker runtime, connector stack, and DI wiring.

Why Python for v1:
- Worker execution plane is already Python/async.
- Existing connector implementations (Postgres/Snowflake/etc.) are Python `SqlConnector` classes.
- Semantic query compiler already exists in Python (`SemanticQueryEngine`).
- Fastest path to production with low operational complexity.

Embedded local compute engine:
- **DuckDB** for local/federated relational operators.
- **Apache Arrow** (`pyarrow`) for intermediate exchange and artifact serialization.

v2 upgrade path:
- Keep planner/IR contracts stable and swap local execution backend with Rust DataFusion via gRPC or Python bindings for stronger vectorized/distributed runtime scaling.

## Planner flow
```mermaid
flowchart LR
    A[Input Query\nSMQ or T-SQL] --> B[Normalize to SQL\nSMQ compiler or sqlglot parser]
    B --> C[Logical Plan IR\nTables Joins Filters GroupBy Order Limit]
    C --> D[Source Binding Resolution\nVirtual Dataset + Federation Workflow]
    D --> E[Rule Optimizer\nPredicate/Projection pushdown\nJoin heuristics\nLimit/Agg pushdown]
    E --> F[Physical Planner\nStage DAG + exchange format]
    F --> G[Physical Plan\nremote_scan/local_compute stages]
```

## Execution DAG lifecycle
```mermaid
flowchart TD
    P[Physical Plan DAG] --> R[Ready Stage Selection]
    R --> S[Stage Execute]
    S --> C{Artifact exists?}
    C -- yes --> H[Reuse cached output]
    C -- no --> W[Write content-hashed Arrow/Parquet artifact]
    H --> M[Emit stage metrics]
    W --> M
    M --> D{Downstream deps resolved?}
    D -- yes --> R
    D -- no --> T[Wait]
    T --> R
    M --> F[Final stage complete]
    F --> O[ResultHandle + fetch_arrow]
```

## Distributed worker scheduling
```mermaid
flowchart LR
    Q[FederatedQueryTool\nexecute_federated_query] --> PL[Planner + DAG]
    PL --> SCH[Scheduler]
    SCH -->|ready stages| EX1[Worker Instance A]
    SCH -->|ready stages| EX2[Worker Instance B]
    SCH -->|ready stages| EX3[Worker Instance N]
    EX1 --> ART[(Artifact Store)]
    EX2 --> ART
    EX3 --> ART
    ART --> SCH
    SCH --> RH[ResultHandle]
```

## Internal API contract
- `FederatedQueryService.execute(query: Union[SMQQuery, str], dialect="tsql", workspace_id=...) -> ResultHandle`
- `FederatedQueryService.fetch_arrow(result_handle) -> pyarrow.Table`
- `FederatedQueryService.explain(query, dialect="tsql", workspace_id=...) -> logical + physical plan`

## Worker tool entrypoint
- `langbridge/apps/worker/langbridge_worker/tools/federated_query_tool.py`
- entrypoint method: `execute_federated_query(query_payload)`

Expected payload fields:
- `workspace_id`
- `query` (SMQ object or SQL string)
- `dialect` (default `tsql`)
- `workflow` (`FederationWorkflow`: virtual dataset tables + source bindings + planning knobs)
- `semantic_model` (required for SMQ)

## At-least-once semantics and idempotency
- Stage outputs are persisted through a content-hash artifact key.
- Stage manifest path is deterministic per `(workspace_id, plan_id, stage_id)`.
- Retries reuse cached stage artifacts when manifest is present.
- Scheduler retries failed stages up to configured `retry_limit`.

## Observability emitted per stage
- runtime ms
- rows written
- bytes written
- source elapsed ms (remote scans)
- attempt count
- cache hit indicator

## Local development
- Federation artifact path env: `FEDERATION_ARTIFACT_DIR`
- Optional planner knobs:
  - `FEDERATION_BROADCAST_THRESHOLD_BYTES`
  - `FEDERATION_PARTITION_COUNT`
  - `FEDERATION_STAGE_MAX_RETRIES`
  - `FEDERATION_STAGE_PARALLELISM`
- Optional compose profile for two isolated Postgres sources:
  - `docker compose --profile federation-sources up federation-db-a federation-db-b`
