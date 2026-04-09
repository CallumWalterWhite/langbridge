# Spec Kit In Langbridge

Use Spec Kit in this repo for larger runtime feature slices where Codex needs
to hold requirements, design, and execution steps together across multiple
modules or surfaces.

## How To Invoke It With Codex

Start Codex in the `langbridge/` repo root and use the project-local skills:

- `$speckit-constitution`
- `$speckit-specify`
- `$speckit-plan`
- `$speckit-tasks`
- `$speckit-implement`

This repo uses the official Codex skills layout under `.agents/skills/` and
the project artifacts under `.specify/`.

## When To Use It

Use Spec Kit when the work affects architecture, runtime contracts, multiple
runtime modules, or multiple surfaces such as API plus SDK, runtime UI,
semantic plus federation, dataset plus sync, or orchestrator plus execution.

Skip it for tiny isolated fixes, narrow refactors, straightforward docs-only
changes, or one-file edits where a full spec would add ceremony without
clarity.

## Expected Workflow For A Larger Feature Slice

1. Run `$speckit-specify` with a runtime-focused feature description.
2. Review `specs/<feature>/spec.md` and make sure the runtime/cloud boundary
   is explicit.
3. Run `$speckit-plan` to map the work to real repo paths, tests, docs, and
   contracts.
4. Run `$speckit-tasks` to break the work into independently testable slices.
5. Run `$speckit-implement` or execute the plan manually in phases.

Use `.specify/memory/constitution.md` and
`.specify/memory/project-guidance.md` as the repo-specific guardrails while
planning and implementing.

## Where Artifacts Live

- Project guidance and constitution: `.specify/memory/`
- Reusable templates: `.specify/templates/`
- Codex skills: `.agents/skills/`
- Feature specs and plans: `specs/<branch-or-feature>/`

## Repo-Specific Notes

- The repo-owned `AGENTS.md` remains authoritative for Codex in this repo.
  Spec Kit is intentionally configured not to rewrite it during planning.
- This setup is for the runtime repo only. Do not use it to plan
  cloud/control-plane work inside `langbridge/`.
