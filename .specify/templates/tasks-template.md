---

description: "Task list template for feature implementation"
---

# Tasks: [FEATURE NAME]

**Input**: Design documents from `/specs/[###-feature-name]/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: For this repo, tests are expected for behavior-changing or architecture-affecting work. Omit them only for docs-only or clearly non-executable changes, and state why.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g. US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Runtime host and services**: `langbridge/runtime/`, `langbridge/client/`, `langbridge/mcp/`, `tests/unit/`, `tests/integration/`
- **Semantic and federation**: `langbridge/semantic/`, `langbridge/federation/`, `tests/semantic/`, `tests/federation/`
- **Connectors and plugins**: `langbridge/connectors/`, `langbridge/plugins/`, `langbridge-connectors/`, `tests/connectors/`
- **Orchestrator work**: `langbridge/orchestrator/`, `tests/orchestrator/`
- **Runtime UI**: `apps/runtime_ui/`, packaged output in `langbridge/ui/static/`, plus any host-facing tests/docs
- **Docs**: `docs/architecture/`, `docs/features/`, `docs/development/`, `docs/insomnia/`, `README.md`

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [ ] T001 Create feature artifacts and directory plan alignment under `specs/[###-feature-name]/`
- [ ] T002 Confirm affected runtime paths and test paths from `plan.md`
- [ ] T003 [P] Add any shared fixtures, sample configs, or schema stubs needed for this feature

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**CRITICAL**: No user story work can begin until this phase is complete

- [ ] T004 Add or refine shared runtime/domain models in `langbridge/...`
- [ ] T005 [P] Add contract validation, normalization, or resolver changes used by multiple stories
- [ ] T006 [P] Add shared service, provider, or planner scaffolding that all stories depend on
- [ ] T007 Add shared host/API or SDK wiring only if every story depends on it
- [ ] T008 Identify shared docs or contract files that must move in lockstep with implementation
- [ ] T009 Add baseline tests or fixtures that establish the new runtime slice

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - [Title] (Priority: P1)

**Goal**: [Brief description of what this story delivers]

**Independent Test**: [How to verify this story works on its own]

### Tests for User Story 1

> **NOTE**: Write these tests first for behavior-changing work and ensure they fail before implementation.

- [ ] T010 [P] [US1] Add focused test coverage in the appropriate test path for the primary runtime slice
- [ ] T011 [P] [US1] Add integration or golden coverage for the independent user journey when applicable

### Implementation for User Story 1

- [ ] T012 [P] [US1] Add or update the primary contract/model files in the selected runtime module
- [ ] T013 [P] [US1] Implement the main service, planner, loader, connector, or UI component for this slice
- [ ] T014 [US1] Wire the user-facing entry point in the relevant API, SDK, orchestrator, or UI path
- [ ] T015 [US1] Add validation, policy enforcement, or error handling for the story's main flow
- [ ] T016 [US1] Update any coupled docs, examples, or API contract files required for this slice
- [ ] T017 [US1] Verify the story works independently through its documented runtime path

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently

---

## Phase 4: User Story 2 - [Title] (Priority: P2)

**Goal**: [Brief description of what this story delivers]

**Independent Test**: [How to verify this story works on its own]

### Tests for User Story 2

- [ ] T018 [P] [US2] Add focused test coverage for the secondary runtime slice
- [ ] T019 [P] [US2] Add integration, golden, or UI validation for the independent user journey when applicable

### Implementation for User Story 2

- [ ] T020 [P] [US2] Add or update the relevant runtime models, planner nodes, loaders, or UI state
- [ ] T021 [US2] Implement the service or feature logic for this story in the chosen module
- [ ] T022 [US2] Wire the affected runtime surface and preserve any required API/SDK/UI consistency
- [ ] T023 [US2] Update supporting docs or examples for this story when needed

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently

---

## Phase 5: User Story 3 - [Title] (Priority: P3)

**Goal**: [Brief description of what this story delivers]

**Independent Test**: [How to verify this story works on its own]

### Tests for User Story 3

- [ ] T024 [P] [US3] Add focused test coverage for the tertiary runtime slice
- [ ] T025 [P] [US3] Add an independent validation path for the user journey when applicable

### Implementation for User Story 3

- [ ] T026 [P] [US3] Add or update the relevant runtime models or UI pieces for this story
- [ ] T027 [US3] Implement the story logic in the selected module or package
- [ ] T028 [US3] Wire the final runtime-facing behavior and document any intentional boundary limits

**Checkpoint**: All user stories should now be independently functional

---

## Phase N: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] TXXX [P] Documentation updates in docs/
- [ ] TXXX Code cleanup and boundary tightening across touched modules
- [ ] TXXX Performance or planner validation across affected runtime paths
- [ ] TXXX [P] Additional targeted tests in the relevant `tests/` subtree
- [ ] TXXX Update `README.md`, `docs/features/*`, `docs/architecture/*`, or `docs/insomnia/*` as needed
- [ ] TXXX Run `quickstart.md` validation and any required UI build or packaging checks

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
- **Polish (Final Phase)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2)
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) but should remain independently testable
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) but should remain independently testable

### Within Each User Story

- Tests should be written and fail before implementation for behavior-changing work
- Contracts and models before service wiring
- Service or planner logic before API, SDK, or UI entry points
- Story documentation before final validation sign-off

### Parallel Opportunities

- Setup tasks marked [P] can run in parallel
- Foundational tasks marked [P] can run in parallel
- Once Foundational completes, user stories can proceed in parallel if they do not fight over the same files
- Test and model tasks marked [P] can run in parallel inside a story

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1
4. Stop and validate the story independently

### Incremental Delivery

1. Complete Setup and Foundational work
2. Deliver User Story 1 and validate it
3. Deliver User Story 2 and validate it
4. Deliver User Story 3 and validate it

### Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to a specific user story
- Each story should be independently completable and testable
- Avoid vague tasks, same-file conflicts, and cloud/control-plane work in this repo
