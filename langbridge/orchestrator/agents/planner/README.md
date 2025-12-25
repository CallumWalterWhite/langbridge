# Planning Agent

The planning agent provides deterministic, policy-aware routing for downstream
orchestration. It does not execute tools. Instead it analyses a user question,
applies routing policies and constraints, and returns an ordered JSON plan that
the supervisor can execute.

## Architecture

```
PlannerRequest -> PlanningAgent.plan()
    ├─ policies.check_policies()  # annotate risks
    ├─ router.choose_route()      # rule/heuristic routing
    ├─ router.build_steps()       # construct ordered steps
    └─ Plan                       # Plan / PlanStep Pydantic models
```

The planner is stateless and side-effect free: identical inputs produce the same
plan output. Guardrails run before routing so risks can be surfaced alongside
plans.

## Models

```python
class PlanningConstraints(BaseModel):
    max_steps: int = 4
    prefer_low_latency: bool = True
    cost_sensitivity: str = "medium"      # "low" | "medium" | "high"
    require_viz_when_chartable: bool = True
    allow_sql_analyst: bool = True
    allow_web_search: bool = True
    allow_deep_research: bool = True
    timebox_seconds: int = 30

class PlannerRequest(BaseModel):
    user_id: str | None
    question: str
    context: dict[str, Any] | None
    constraints: PlanningConstraints

class PlanStep(BaseModel):
    id: str
    agent: str           # "Analyst" | "Visual" | "WebSearch" | "DocRetrieval" | "Clarify"
    input: dict[str, Any]
    expected_output: dict[str, Any]

class Plan(BaseModel):
    route: str           # "SimpleAnalyst" | "AnalystThenVisual" | "WebSearch" | "DeepResearch" | "Clarify"
    steps: list[PlanStep]
    justification: str
    user_summary: str
    assumptions: list[str] = []
    risks: list[str] = []
```

## Route Criteria

| Route                | When it applies                                                                     |
|----------------------|--------------------------------------------------------------------------------------|
| `SimpleAnalyst`      | SQL-amenable question with clear entity/time cues. Emphasises low latency.           |
| `AnalystThenVisual`  | SQL intent plus chart/visual cues, or chartable aggregations when viz is required.   |
| `WebSearch`          | Explicit request to search the public web (news, sources, articles).                 |
| `DeepResearch`       | Document/narrative synthesis, multi-source analysis, optional data verification.     |
| `Clarify`            | Ambiguous intent blocks safe execution; planner returns one clarifying question.     |

Routing is rule-first and heuristic-second:

1. Guardrails (PII, destructive SQL) record risks – they do not block.
2. Ambiguity triggers `Clarify`.
3. Hard constraints honour `allow_deep_research`, `max_steps`, and `require_viz_when_chartable`.
4. Remaining candidates receive deterministic scores.

Tie-breaking order: `SimpleAnalyst` → `AnalystThenVisual` → `DeepResearch`.

## Plan Construction

The planner emits an ordered list of steps where each step references an agent
and articulates both input payload and expected output. Cross-step references
use `step-{n}` identifiers (e.g. the Visual step references analyst results).

Example (`AnalystThenVisual`):

```jsonc
{
  "route": "AnalystThenVisual",
  "steps": [
    {
      "id": "step-1",
      "agent": "Analyst",
      "input": {"question": "..."},
      "expected_output": {"rows": "tabular_result_set", "schema": "column_metadata"}
    },
    {
      "id": "step-2",
      "agent": "Visual",
      "input": {"rows_ref": "step-1", "user_intent": "ranked_highlights"},
      "expected_output": {"viz_spec": "json_visualization_spec"}
    }
  ],
  "justification": "SQL intent with visualization cues; aggregations suitable for charting.",
  "user_summary": "I'll query the data and then provide a companion chart."
}
```

## Constraints Support

- `max_steps`: routes exceeding the limit are never selected; steps are truncated accordingly.
- `prefer_low_latency`: penalises `DeepResearch`.
- `cost_sensitivity`: further adjusts the research score when `high`.
- `require_viz_when_chartable`: upgrades routes that look chartable when two steps are allowed.
- `allow_sql_analyst`: disables SQL analyst routes entirely.
- `allow_web_search`: disables the `WebSearch` route entirely.
- `allow_deep_research`: disables the `DeepResearch` route entirely.
- `timebox_seconds`: surfaced in doc retrieval step inputs and assumptions.

## Extending the Planner

- Add new routes by extending `RouteName`, updating routing heuristics, and
  providing `build_steps` logic for the route.
- Refine policy checks in `policies.py` for organisation-specific guardrails.
- Update tests under `tests/orchestrator/agents/planner` to cover new behaviour.
