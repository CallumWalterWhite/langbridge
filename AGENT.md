# Agent Implementation Guide

This doc captures the conventions already used in this codebase for building agent-facing APIs, services, and client pages.

## Client (Next.js) patterns
- Routing: pages live under `client/src/app/(app)/...`. Group feature pages together (e.g., `/agents/definitions`, `/agents/llm-connections`). Use nested routes for create/edit (`create`, `[id]`).
- Data fetching: use `@tanstack/react-query` (`useQuery`, `useMutation`, `useQueryClient`) with stable query keys; invalidate keys after mutations. Keep orchestration HTTP helpers in `client/src/orchestration/<feature>/index.ts` and type defs in `types.ts`. Normalize API responses (snake_case → camelCase) at the client boundary.
- UI composition: reuse shared primitives in `client/src/components/ui` (Button, Input, Textarea, Select, Badge, Skeleton, Tabs, Toast). Wrap main sections in `surface-panel` classes with rounded corners and soft shadows; avoid unstyled elements. Provide loading/error/empty states (see LLM connections and agent definitions list pages) and inline validation toasts via `useToast`.
- Workspace context: read org/project defaults via `useWorkspaceScope`; block create flows if an org is not selected. Pass org/project IDs to APIs when needed.
- Forms: keep local `FormState`, validate required fields early, and show inline toasts on failure. For structured payloads, stringify/parse JSON defensively (see agent builder form). Use `useMemo` for lookup maps and render-friendly sorts (e.g., updated desc). Include navigation helpers (`useRouter`) to redirect after success.
- Navigation aids: add secondary CTAs to related features (e.g., “Agent builder” button from the LLM connections page).

## Agent definition model (orchestrator)
- Pydantic model lives in `orchestrator/definitions/model.py` (`AgentDefinitionModel`). It includes:
  - PromptContract: system prompt, user instructions, style guidance.
  - Memory: strategy (`none`, `transient`, `conversation`, `long_term`, `vector`, `database`) plus TTL/vector index/DB table.
  - Tools: bindings with optional connector_id and config payloads.
  - Data access policy: allow/deny connector IDs, optional PII handling, row-level filter.
  - Execution behavior: single_step vs iterative, iteration/step caps, allow_parallel_tools.
  - Output schema: format (text/markdown/json/yaml), optional JSON schema and markdown template.
  - Guardrails: moderation_enabled, blocked_categories, regex_denylist, escalation message.
  - Observability: log_level, emit_traces, capture_prompts, audit_fields.
  - Defaults: extra fields ignored; enums are string-backed.

## Backend API & service patterns
- Stack: FastAPI with dependency-injector. Routers under `api/v1/` declare dependencies using `Depends(Provide[Container.<provider>])`. Auth enforced via `get_current_user` (pulls `request.state.user` set by AuthMiddleware/JWT).
- CRUD shape: 
  - POST returns created resource, often 201. 
  - GET collection returns list; GET by id 404s if missing. 
  - PUT updates by id; returns 404 on missing. 
  - DELETE returns 204; surface business validation as 404/400.
- Agents endpoints (`api/v1/agents.py`):
  - LLM connections: `/agents/llm-connections` CRUD + `/test` (no auth bypass). 
  - Agent definitions: `/agents/definitions` CRUD.
- Services (`services/agent_service.py`):
  - Authorization: `__check_authorized` ensures user belongs to at least one org/project linked to the LLM connection; bypassed when `is_internal_service_call()` is set (context var from `services/service_utils.py`).
  - LLM connection CRUD validates access via `UserAuthorizedProvider` and tests new keys with `LLMConnectionTester`.
  - Agent definitions tie to an `llm_connection_id`; all CRUD paths load the connection and re-use authorization. Updates are partial; missing records return `None` so handlers can 404.
  - Helper `_get_llm_connection` raises on missing connections.
- DI wiring: `ioc/container.py` registers repositories and services (including environment_service) with async sessions. Add new services here and wire routers with `Provide`.

## Orchestration client helpers
- Feature modules under `client/src/orchestration/<feature>` export typed helpers. Follow the LLM connections/agent definitions module:
  - Define API response and client-facing types in `types.ts`.
  - Add normalize/serialize helpers at the boundary.
  - Keep BASE_PATH constants and compose URLSearchParams for org/project scoping.
  - Re-export types for convenient imports.

## Building new agent-facing UI
- Create list and form pages under `client/src/app/(app)/agents/<feature>` with matching patterns: 
  - List page: query + loading/error/empty states; actions for edit/delete; refresh button wired to `refetch`.
  - Create/edit page: share a form component that takes `mode`, optional initial data, and `onComplete` to redirect.
  - Use `surface-panel` layout, concise typography, and add helper text. Lean on Lucide icons (Bot, RefreshCw, Plus, ArrowRight, Sparkles) for affordances.
  - Keep JSON inputs resilient (stringify/parse with fallbacks) and allow comma-separated lists for IDs.

## Notes on auth and internal calls
- External API traffic must include a session cookie for `AuthMiddleware`; handlers expect `current_user` via `get_current_user` and will 401 otherwise.
- Internal orchestrator/service callers can mark methods with `@internal_service` and invoke via `call_internal_service`; the context flag skips authorization checks. Do not expose public routes that rely on this bypass.

## Environment settings (encrypted KV)
- Organization-scoped settings live in `organisation_environment_settings`. The service (`services/environment_service.py`) encrypts values with `ConfigCrypto` and per-org AAD. Provide a keyring via env vars or fall back to a derived local key. Repository: `repositories/environment_repository.py`.

## Migration reminders
- Agent definitions now reference `llm_connection_id` (UUID). Ensure DB migrations rename/convert the column if upgrading existing data.
