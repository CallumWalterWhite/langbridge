# Agent Features

Langbridge agents are orchestrated analysis workers that can combine semantic, SQL, and external tools.

## Agent Stack

- Planner agent for policy-aware route selection.
- Supervisor/orchestrator flow for multi-step execution.
- Tooling integrations (SQL analyst, semantic retrieval, web/doc workflows).

## Relationship to Data Execution

- Agents do not bypass data execution policy.
- Structured query workloads are routed through control plane and executed in worker runtime.
- Federation and SQL guardrails apply consistently to agent-initiated and user-initiated workloads.

## Core Value

Agents are first-class consumers of the same platform primitives:
- Semantic layer.
- SQL workbench and SQL job APIs.
- Federated execution engine.
- Runtime routing (hosted vs customer runtime).
