# Control Plane

The Control Plane is the policy, orchestration, and product surface of Langbridge.

## Responsibilities

- Authentication, tenancy, and RBAC.
- API contracts and request validation.
- Orchestration of semantic, SQL, and agent workflows.
- Workspace and SQL policy management.
- Runtime registry for customer execution runtimes.
- Task dispatch into hosted or customer runtime execution planes.
- Audit record creation and job metadata persistence.

## Main Components

- API app: `langbridge/apps/api/langbridge_api`
- UI app: `client/`
- Orchestrator package: `langbridge/packages/orchestrator`
- Shared contracts/models: `langbridge/packages/common`
- Messaging contracts: `langbridge/packages/messaging`

## Control Plane to Execution Plane Boundary

The control plane never executes heavy data queries directly.

Instead it:
1. Validates policy and scope.
2. Creates/queues job payloads.
3. Dispatches to execution targets:
   - Hosted workers (default hosted mode).
   - Customer runtime workers (hybrid mode via edge task transport).
4. Receives status/results and serves UI/API clients.

## Key API Domains

- `/api/v1/sql/*`: SQL workbench lifecycle (execute/cancel/jobs/results/history/saved/policies).
- `/api/v1/semantic-query/*`: semantic query orchestration and metadata.
- `/api/v1/runtimes/*`: secure runtime registration and heartbeat/capability updates.
- `/api/v1/edge/tasks/*`: edge task pull/ack/result/fail transport for customer runtime workers.

## Security Model

- User auth and workspace scoping at API boundary.
- Runtime auth using short-lived runtime credentials.
- Explicit execution mode routing (hosted vs customer runtime).
- Auditable job metadata (user/workspace/connection/fingerprints/timestamps).
