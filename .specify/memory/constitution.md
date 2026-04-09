<!--
Sync Impact Report
Version change: template -> 1.0.0
Modified principles:
- template Principle 1 -> I. Runtime-First Product Ownership
- template Principle 2 -> II. Explicit Runtime Contracts Over Heuristic Behavior
- template Principle 3 -> III. Dataset-First, Boundary-Clean Design
- template Principle 4 -> IV. Deliberate Change, Minimal Shims, SOLID Boundaries
- template Principle 5 -> V. Architecture Changes Require Tests, Docs, and Surface Consistency
Added sections:
- Runtime Design Constraints
- Delivery Workflow & Quality Gates
Removed sections:
- none
Templates requiring updates:
- updated .specify/templates/constitution-template.md
- updated .specify/templates/spec-template.md
- updated .specify/templates/plan-template.md
- updated .specify/templates/tasks-template.md
- updated .specify/memory/project-guidance.md
- updated docs/development/spec-kit.md
Deferred items:
- none
-->
# Langbridge Runtime Constitution

## Core Principles

### I. Runtime-First Product Ownership
All work in `langbridge/` MUST serve the Langbridge runtime product:
embedded use, local development, self-hosted deployment, or
customer-managed runtime execution. Capabilities whose primary purpose is
tenant management, hosted operations, cloud control planes, billing, or
product-web administration MUST stay out of this repository and belong in
`langbridge-cloud/` or an explicit integration boundary.

### II. Explicit Runtime Contracts Over Heuristic Behavior
Runtime behavior MUST be expressed through explicit contracts, schemas,
and domain models rather than connector-family guesses, silent fallbacks,
or ambiguous aliases. Dataset-owned contracts, capability flags, relation
identity, and normalized semantic/runtime models are preferred over ad
hoc inference. New work SHOULD remove ambiguity rather than preserve it.

### III. Dataset-First, Boundary-Clean Design
Datasets are the primary structured execution contract between connectors
and higher-level runtime surfaces. New structured execution work MUST
keep responsibilities explicit across `langbridge.runtime`,
`langbridge.semantic`, `langbridge.federation`, `langbridge.connectors`,
`langbridge.plugins`, `langbridge.orchestrator`, `langbridge.mcp`, and
`apps/runtime_ui`. Connector packages SHOULD stay thin when shared
runtime behavior can live cleanly in core runtime code.

### IV. Deliberate Change, Minimal Shims, SOLID Boundaries
Changes MUST preserve cohesive module boundaries and prefer small,
composable interfaces. Backward-compatibility shims, dual-path behavior,
and legacy aliases MUST NOT be added by default; they require explicit
justification in the spec or plan. Breaking changes are acceptable when
they simplify the runtime and are documented with clear migration notes.

### V. Architecture Changes Require Tests, Docs, and Surface Consistency
Architecture-affecting or behavior-changing work MUST ship with the
tests, documentation, and interface updates needed to prove the new
behavior. When a change touches multiple runtime surfaces, the spec and
plan MUST keep runtime API, SDK, packaged UI, MCP, and docs consistent,
or explicitly document any intentional asymmetry.

## Runtime Design Constraints

- Preserve runtime portability and self-hosted friendliness. The runtime
  MUST remain usable without a Langbridge Cloud dependency.
- Keep runtime-core identity thin and workspace-scoped:
  `workspace_id`, `actor_id`, `roles`, and `request_id`.
- Prefer dataset-owned execution contracts and explicit
  `materialization_mode`, `source`, `sync`, and semantic model bindings
  over connector-owned special cases.
- Keep runtime UI work runtime-owned and feature-gated. Do not introduce
  unrelated product-web or hosted admin flows here.
- Treat preview scale-out seams as preview unless a feature explicitly
  targets them; v1 planning defaults to the single runtime host.

## Delivery Workflow & Quality Gates

- Use Spec Kit for cross-module, architecture-affecting, or multi-surface
  runtime work. Tiny refactors, isolated bug fixes, and docs-only edits do
  not require full spec artifacts.
- Every spec MUST state why the feature belongs in `langbridge/`, what
  remains out of scope for `langbridge-cloud/`, and which runtime surfaces
  are affected.
- Every plan MUST map work to real repository paths, identify required
  docs/tests, and record any compatibility or migration decisions.
- Every task list MUST group work into independently testable slices so
  runtime changes can land incrementally.
- Architecture, API, semantic, federation, dataset, connector, agent, or
  runtime UI changes MUST include targeted pytest coverage and any needed
  docs updates before implementation is considered complete.

## Governance

This constitution governs Spec Kit usage for `langbridge/`. Reviews and
plans MUST verify runtime ownership, portability, explicit contracts,
clean boundaries, and the required docs/tests. Amendments use semantic
versioning: MAJOR for incompatible principle changes, MINOR for new or
materially expanded guidance, PATCH for clarifications. The authoritative
companion guidance for this repo is:

- `AGENTS.md`
- `docs/architecture/*`
- `.specify/memory/project-guidance.md`

**Version**: 1.0.0 | **Ratified**: 2026-04-08 | **Last Amended**: 2026-04-08
