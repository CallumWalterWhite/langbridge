# Hybrid Deployment Architecture

Langbridge supports hybrid deployment by separating control and execution planes.

## Deployment Modes

- **Hosted**: control plane + worker runtime are hosted by Langbridge.
- **Hybrid**: control plane hosted; worker runtime runs in customer network.
- **Self-hosted**: control + execution planes run in customer-managed infrastructure.

## Runtime Registration Flow

```mermaid
sequenceDiagram
    participant Admin as Org Admin
    participant CP as Control Plane API
    participant CR as Customer Runtime Worker

    Admin->>CP: POST /api/v1/runtimes/{org_id}/tokens
    CP-->>Admin: one-time registration token
    CR->>CP: POST /api/v1/runtimes/register (token + runtime metadata)
    CP-->>CR: runtime identity + access token
    loop heartbeat
        CR->>CP: POST /api/v1/runtimes/heartbeat
        CP-->>CR: liveness ack + token refresh
    end
    CR->>CP: POST /api/v1/runtimes/capabilities
    CP-->>CR: capability update accepted
```

## Edge Task Transport Flow

```mermaid
flowchart LR
    CP[Control Plane Dispatch] --> PULL[/POST edge/tasks/pull/]
    PULL --> CR[Customer Runtime Worker]
    CR --> ACK[/POST edge/tasks/ack/]
    CR --> RESULT[/POST edge/tasks/result/]
    CR --> FAIL[/POST edge/tasks/fail/]
    RESULT --> CP
```

## Security and Isolation

- Runtime registration tokens are one-time and scoped.
- Runtime principals are authenticated for heartbeat/capability/task transport.
- Task routing is organization-aware and capability-aware.
- Results ingestion is idempotent through request IDs and payload hashing.
