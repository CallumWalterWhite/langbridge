# Langbridge Spec Kit Project Guidance

## Repo Identity

- `langbridge/` is the runtime product, not the cloud/control-plane repo.
- Features here must work for embedded, local, self-hosted, or
  customer-managed runtime execution.
- If a capability primarily manages hosted operations, tenancy, billing,
  orchestration for a control plane, or unrelated product-web concerns, it
  belongs in `langbridge-cloud/`, not here.

## Runtime Architecture Map

- `langbridge/runtime/`: host construction, API, auth, services, providers,
  runtime metadata, execution services.
- `langbridge/semantic/`: semantic contracts, loaders, unified model support.
- `langbridge/federation/`: planner and execution substrate for structured,
  cross-source execution.
- `langbridge/connectors/` and `langbridge/plugins/`: core connector runtime,
  plugin registration, shared connector contracts.
- `langbridge-connectors/`: thin external connector packages when runtime
  behavior can stay generic in core.
- `langbridge/orchestrator/`: runtime-safe agent and tool orchestration.
- `langbridge/client/`: SDK and local/runtime-host adapters.
- `apps/runtime_ui/` and `langbridge/ui/`: runtime-owned UI source and bundle.

## V1 Planning Defaults

- Treat the single runtime host as the primary v1 deployment surface.
- Preserve the dataset-first direction:
  `materialization_mode`, `source`, `sync`, capability flags, and relation
  identity should stay explicit.
- Prefer explicit domain models and validation over heuristic fallbacks.
- Avoid adding compatibility shims unless the spec explicitly justifies them.
- Keep API, SDK, runtime UI, MCP, and docs aligned when a feature touches
  those surfaces.

## Common Feature Slice Patterns

- Runtime architecture slices: host wiring, providers, services, runtime API
  layering, auth/context, execution-plane behavior.
- Federation improvements: planner behavior, pushdown, workflow generation,
  execution metadata, golden plans/results.
- Semantic hardening: canonical semantic contracts, loaders, validation,
  unified models, compiled SQL behavior.
- Dataset, sync, and modeling work: dataset-owned contracts, sync state,
  capability validation, dataset metadata, source modeling.
- Agent and orchestrator work: tool bindings, runtime guardrails, thread/run
  behavior, analyst workflows.
- Runtime UI slices: runtime-owned product surfaces only, feature-gated and
  aligned with runtime APIs.

## Expected Docs And Tests

- Tests usually live in `tests/unit/`, `tests/integration/`, `tests/semantic/`,
  `tests/federation/`, `tests/connectors/`, and `tests/orchestrator/`.
- Docs usually live in `docs/architecture/`, `docs/features/`,
  `docs/development/`, `docs/api.md`, `docs/datasets.md`,
  `docs/semantic-model.md`, and `docs/insomnia/langbridge-runtime-api.yaml`.
- Architecture-affecting work should include targeted tests and docs updates.

## Typical Validation Commands

- `pytest -q tests`
- `pytest -q tests/unit`
- `pytest -q tests/integration`
- `pytest -q tests/semantic`
- `pytest -q tests/federation`
- `cd apps/runtime_ui && npm run build` when UI source changes
