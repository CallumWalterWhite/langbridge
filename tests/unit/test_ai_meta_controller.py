import asyncio

from langbridge.ai import (
    AgentIOContract,
    AgentResult,
    AgentRegistry,
    AgentResultStatus,
    AgentRoutingSpec,
    AgentSpecification,
    AgentTask,
    AgentTaskKind,
    AnalystAgentConfig,
    BaseAgent,
    MetaControllerAgent,
    PlanReviewAction,
    FinalReviewAction,
    FinalReviewReasonCode,
    PlanReviewReasonCode,
    VerificationReasonCode,
)
from langbridge.ai.agents import (
    AnalystAgent,
    PresentationAgent,
)
from langbridge.ai.orchestration.execution import PlanExecutionState
from langbridge.ai.orchestration.plan_review import PlanReviewAgent
from langbridge.ai.orchestration.planner import ExecutionPlan, PlannerAgent, PlanStep
from langbridge.ai.orchestration.verification import VerificationOutcome
from langbridge.ai.tools.charting import ChartingTool
from langbridge.ai.tools.web_search import WebSearchResultItem, WebSearchTool


def _run(coro):
    return asyncio.run(coro)


def _analyst_config(*, research_enabled: bool = False, web_search_enabled: bool = False) -> AnalystAgentConfig:
    return AnalystAgentConfig.model_validate(
        {
            "name": "analyst",
            "analyst_scope": {
                "semantic_models": ["commerce"],
                "datasets": ["orders"],
                "query_policy": "semantic_preferred",
            },
            "research_scope": {"enabled": research_enabled},
            "web_search_scope": {"enabled": web_search_enabled},
        }
    )


class _FakeLLMProvider:
    async def acomplete(self, prompt: str, **kwargs):
        if "Decide Langbridge agent route" in prompt:
            if "Dependency ordered request" in prompt:
                return (
                    '{"action":"plan","rationale":"Dependency-aware plan required.",'
                    '"agent_name":null,"task_kind":null,"input":{},'
                    '"clarification_question":null,"plan_guidance":"Honor step dependencies."}'
                )
            if "Show it" in prompt:
                return (
                    '{"action":"clarify","rationale":"Question lacks metric and dataset scope.",'
                    '"agent_name":null,"task_kind":null,"input":{},'
                    '"clarification_question":"Which metric and dataset should I use?",'
                    '"plan_guidance":null}'
                )
            if "Ambiguous planned request" in prompt:
                return (
                    '{"action":"plan","rationale":"Planner should decide whether clarification is needed.",'
                    '"agent_name":null,"task_kind":null,"input":{},'
                    '"clarification_question":null,"plan_guidance":"Resolve ambiguity before execution."}'
                )
            if "Search the web" in prompt:
                return (
                    '{"action":"direct","rationale":"One analyst can perform source-backed research directly.",'
                    '"agent_name":"analyst","task_kind":"analyst","input":{"agent_mode":"research"},'
                    '"clarification_question":null,"plan_guidance":null}'
                )
            if "broken-analyst" in prompt:
                return (
                    '{"action":"direct","rationale":"Test selects weak direct agent first.",'
                    '"agent_name":"broken-analyst","task_kind":"analyst","input":{},'
                    '"clarification_question":null,"plan_guidance":null}'
                )
            return (
                '{"action":"direct","rationale":"Single analyst can answer from provided context.",'
                '"agent_name":"analyst","task_kind":"analyst","input":{},'
                '"clarification_question":null,"plan_guidance":null}'
                )
        if "Build Langbridge execution plan" in prompt:
            if "Ambiguous planned request" in prompt:
                return (
                    '{"route":"planned:clarification",'
                    '"rationale":"Cannot plan safely without metric scope.",'
                    '"clarification_question":"Which metric and dataset should I use?",'
                    '"steps":[]}'
                )
            if "broken-analyst" in prompt:
                return (
                    '{"route":"planned:recovery","rationale":"Avoid failed agent and recover with analyst.",'
                    '"steps":[{"agent_name":"analyst","task_kind":"analyst",'
                    '"question":"Explain this result","input":{},"depends_on":[]}]}'
                )
            return (
                '{"route":"planned:research","rationale":"Use source-backed research mode.",'
                '"steps":[{"agent_name":"analyst","task_kind":"analyst",'
                '"question":"Search the web and then explain latest sources for Langbridge",'
                '"input":{"mode":"research"},"depends_on":[]}]}'
            )
        if "Choose the next execution mode" in prompt:
            if "Search the web" in prompt:
                return '{"mode":"research","reason":"web research requested"}'
            return '{"mode":"context_analysis","reason":"structured result available"}'
        if "Review the final Langbridge answer package" in prompt:
            if "Ambiguous revenue request" in prompt:
                return (
                    '{"action":"ask_clarification","reason_code":"ambiguous_question",'
                    '"rationale":"Need metric scope before finalizing.",'
                    '"issues":["Metric scope is ambiguous."],"updated_context":{"needs_metric_scope":true},'
                    '"clarification_question":"Which revenue metric should I use?"}'
                )
            return (
                '{"action":"approve","reason_code":"grounded_complete",'
                '"rationale":"Answer is grounded in the supplied evidence.",'
                '"issues":[],"updated_context":{},"clarification_question":null}'
            )
        if "Create a chart specification" in prompt:
            return '{"chart_type":"bar","title":"Revenue by region","x":"region","y":"revenue"}'
        if "Synthesize source-backed research" in prompt:
            return (
                '{"synthesis":"Source-backed synthesis for Langbridge.",'
                '"findings":[{"insight":"Runtime reference found.","source":"https://example.test/langbridge"}],'
                '"follow_ups":[]}'
            )
        if "Compose the final Langbridge response" in prompt:
            if "Mode: clarification" in prompt:
                if "Which revenue metric should I use?" in prompt:
                    return (
                        '{"summary":"Clarification needed.",'
                        '"result":{},"visualization":null,"research":{},'
                        '"answer":"Which revenue metric should I use?",'
                        '"diagnostics":{"mode":"clarification"}}'
                    )
                return (
                    '{"summary":"Clarification needed.",'
                    '"result":{},"visualization":null,"research":{},'
                    '"answer":"Which metric and dataset should I use?",'
                    '"diagnostics":{"mode":"clarification"}}'
                )
            if "Analyst recovered answer." in prompt:
                return (
                    '{"summary":"Analyst recovered answer.",'
                    '"result":{},"visualization":null,"research":{},'
                    '"answer":"Analyst recovered answer.","diagnostics":{"mode":"test"}}'
                )
            return (
                '{"summary":"Final answer from verified outputs.",'
                '"result":{},"visualization":null,'
                '"research":{"synthesis":"Source-backed synthesis for Langbridge."},'
                '"answer":"Final answer from verified outputs.","diagnostics":{"mode":"test"}}'
            )
        if "Analyze verified Langbridge result data" in prompt:
            return '{"analysis":"Analyzed verified result data.","result":{"columns":[],"rows":[]}}'
        return '{"analysis":"Analysis complete."}'

    async def create_embeddings(self, texts, embedding_model=None):
        return [[1.0] for _ in texts]


class _FakeWebSearchProvider:
    name = "fake-web"

    async def search_async(self, query: str, **kwargs):
        return [
            WebSearchResultItem(
                title="Langbridge docs",
                url="https://example.test/langbridge",
                snippet="Langbridge runtime reference.",
                source=self.name,
                rank=1,
            )
        ]


class _AnswerAliasRouteLLMProvider(_FakeLLMProvider):
    async def acomplete(self, prompt: str, **kwargs):
        if "Decide Langbridge agent route" in prompt:
            return (
                '{"action":"direct","rationale":"Alias route bug regression.",'
                '"agent_name":"analyst","task_kind":"analyst",'
                '"input":{"agent_mode":"answer"},'
                '"clarification_question":null,"plan_guidance":null}'
            )
        return await super().acomplete(prompt, **kwargs)


class _ReviseThenApproveLLMProvider(_FakeLLMProvider):
    def __init__(self) -> None:
        self.final_review_calls = 0

    async def acomplete(self, prompt: str, **kwargs):
        if "Review the final Langbridge answer package" in prompt:
            self.final_review_calls += 1
            if self.final_review_calls == 1:
                return (
                    '{"action":"revise_answer","reason_code":"missing_caveat_or_framing",'
                    '"rationale":"Needs tighter caveats.",'
                    '"issues":["Add the missing caveat."],"updated_context":{"needs_caveat":true},'
                    '"clarification_question":null}'
                )
            return (
                '{"action":"approve","reason_code":"grounded_complete",'
                '"rationale":"Revised answer is grounded.",'
                '"issues":[],"updated_context":{},"clarification_question":null}'
            )
        if "Compose the final Langbridge response" in prompt and "Revised answer." in prompt:
            return (
                '{"summary":"Revised answer.",'
                '"result":{},"visualization":null,"research":{},'
                '"answer":"Revised answer.","diagnostics":{"mode":"test"}}'
            )
        return await super().acomplete(prompt, **kwargs)


def _presentation(llm: _FakeLLMProvider) -> PresentationAgent:
    return PresentationAgent(llm_provider=llm, charting_tool=ChartingTool(llm_provider=llm))


def _controller() -> MetaControllerAgent:
    llm = _FakeLLMProvider()
    registry = AgentRegistry(
        [
            AnalystAgent(
                llm_provider=llm,
                config=_analyst_config(research_enabled=True, web_search_enabled=True),
                web_search_tool=WebSearchTool(provider=_FakeWebSearchProvider()),
            ),
        ]
    )
    return MetaControllerAgent(registry=registry, llm_provider=llm, presentation_agent=_presentation(llm))


def test_meta_controller_routes_simple_analyst_question_directly() -> None:
    run = _run(
        _controller().handle(
            question="Show revenue by region",
            context={"semantic_model_id": "commerce", "result": {"columns": [], "rows": []}},
        )
    )

    assert run.execution_mode == "direct"
    assert run.status == "completed"
    assert run.plan.route == "direct:analyst"
    assert [step.agent_name for step in run.plan.steps] == ["analyst"]
    assert run.plan.steps[0].expected_output.required_keys == ["analysis", "result", "evidence", "review_hints"]
    assert all(item.passed for item in run.verification)
    assert all(item.reason_code == VerificationReasonCode.passed for item in run.verification)
    assert run.review_decisions[-1].action == PlanReviewAction.finalize
    assert run.review_decisions[-1].reason_code == PlanReviewReasonCode.all_steps_completed
    assert run.final_review["action"] == FinalReviewAction.approve.value
    assert run.final_review["reason_code"] == FinalReviewReasonCode.grounded_complete.value
    assert run.final_result["summary"] == "Final answer from verified outputs."
    assert run.final_result["visualization"] is None


def test_meta_controller_routes_single_analyst_web_research_directly() -> None:
    run = _run(
        _controller().handle(
            question="Search the web and then explain latest sources for Langbridge"
        )
    )

    assert run.execution_mode == "direct"
    assert run.status == "completed"
    assert run.plan.route == "direct:analyst"
    assert [step.agent_name for step in run.plan.steps] == ["analyst"]
    assert run.plan.steps[0].task_kind == AgentTaskKind.analyst
    assert run.plan.steps[0].input["agent_mode"] == "research"
    assert run.plan.steps[0].expected_output.required_keys == [
        "analysis",
        "result",
        "synthesis",
        "sources",
        "findings",
    ]
    assert "mode" not in run.plan.steps[0].input
    assert all(item.passed for item in run.verification)
    assert run.review_decisions[-1].reason_code == PlanReviewReasonCode.all_steps_completed
    assert run.final_result["research"]["synthesis"].startswith("Source-backed")


def test_meta_controller_can_ask_clarification_before_execution() -> None:
    run = _run(_controller().handle(question="Show it"))

    assert run.execution_mode is None
    assert run.status == "clarification_needed"
    assert run.plan.route == "clarification"
    assert run.verification == []
    assert run.final_result["answer"] == "Which metric and dataset should I use?"
    assert run.diagnostics["stop_reason"] == "clarification"


def test_final_review_can_request_clarification_before_presentation() -> None:
    llm = _FakeLLMProvider()
    controller = MetaControllerAgent(
        registry=AgentRegistry([_RecoveringAnalystAgent()]),
        llm_provider=llm,
        presentation_agent=_presentation(llm),
    )

    run = _run(controller.handle(question="Ambiguous revenue request"))

    assert run.execution_mode == "direct"
    assert run.status == "clarification_needed"
    assert run.final_review["action"] == FinalReviewAction.ask_clarification.value
    assert run.final_review["reason_code"] == FinalReviewReasonCode.ambiguous_question.value
    assert run.final_review["clarification_question"] == "Which revenue metric should I use?"
    assert run.final_result["answer"] == "Which revenue metric should I use?"
    assert run.diagnostics["stop_reason"] == "final_review_clarification"


def test_final_review_revise_answer_reruns_latest_step_without_planner_replan() -> None:
    llm = _ReviseThenApproveLLMProvider()
    agent = _RevisableAnalystAgent()
    controller = MetaControllerAgent(
        registry=AgentRegistry([agent]),
        llm_provider=llm,
        planner=_PlannerShouldNotReplan(),
        presentation_agent=_presentation(llm),
        max_replans=1,
    )

    run = _run(controller.handle(question="Revise this answer"))

    assert run.execution_mode == "planned"
    assert run.status == "completed"
    assert agent.calls == 2
    assert agent.contexts[1]["final_review_rationale"] == "Needs tighter caveats."
    assert agent.contexts[1]["final_review_issues"] == ["Add the missing caveat."]
    assert run.final_review["action"] == FinalReviewAction.approve.value
    assert run.final_review["reason_code"] == FinalReviewReasonCode.grounded_complete.value
    assert run.final_result["answer"] == "Revised answer."
    assert run.diagnostics["replan_count"] == 1


def test_planner_can_return_clarification_instead_of_empty_plan_failure() -> None:
    run = _run(_controller().handle(question="Ambiguous planned request"))

    assert run.execution_mode == "planned"
    assert run.status == "clarification_needed"
    assert run.plan.route == "planned:clarification"
    assert run.final_result["answer"] == "Which metric and dataset should I use?"
    assert run.diagnostics["clarification_source"] == "planner"


def test_planner_replan_keeps_only_analyst_available_when_avoid_list_would_empty_candidates() -> None:
    llm = _FakeLLMProvider()
    planner = PlannerAgent(llm_provider=llm)
    analyst = AnalystAgent(llm_provider=llm, config=_analyst_config())
    failed_step = PlanStep(
        step_id="step-1",
        agent_name=analyst.specification.name,
        task_kind=AgentTaskKind.analyst,
        question="Analyze commerce performance",
        input={},
        expected_output=analyst.specification.output_contract,
    )
    state = PlanExecutionState(
        original_question="Analyze commerce performance",
        current_plan=ExecutionPlan(
            route="direct:analyst",
            steps=[failed_step],
            rationale="Use the only analyst.",
            requires_pev=True,
        ),
        replan_count=1,
        context={"failed_agent": analyst.specification.name},
    )
    state.record(
        step=failed_step,
        result=analyst.build_result(
            task=AgentTask(task_id="step-1", task_kind=AgentTaskKind.analyst, question="Analyze commerce performance"),
            status=AgentResultStatus.failed,
            output={},
            error="Execution failed: Binder Error: Cannot compare VARCHAR and DATE.",
        ),
        verification=VerificationOutcome(
            passed=False,
            step_id="step-1",
            agent_name=analyst.specification.name,
            message="Execution failed: Binder Error: Cannot compare VARCHAR and DATE.",
            reason_code=VerificationReasonCode.non_succeeded_status,
        ),
    )

    plan = _run(
        planner.replan(
            state=state,
            context_updates={"retry_hint": "Cast the date column before filtering."},
            specifications=[analyst.specification],
        )
    )

    assert [step.agent_name for step in plan.steps] == [analyst.specification.name]


def test_planner_does_not_emit_stale_avoid_agents_when_only_candidate_remains() -> None:
    class _RecordingPlannerLLM(_FakeLLMProvider):
        def __init__(self) -> None:
            self.prompts: list[str] = []

        async def acomplete(self, prompt: str, **kwargs):
            self.prompts.append(prompt)
            return (
                '{"route":"planned","rationale":"Retry with the only analyst.",'
                '"steps":[{"agent_name":"analyst","task_kind":"analyst","question":"Retry analysis","input":{},"depends_on":[]}]}'
            )

    llm = _RecordingPlannerLLM()
    planner = PlannerAgent(llm_provider=llm)
    analyst = AnalystAgent(llm_provider=llm, config=_analyst_config())
    state = PlanExecutionState(
        original_question="Retry analysis",
        current_plan=ExecutionPlan(
            route="planned",
            steps=[],
            rationale="initial",
            requires_pev=True,
        ),
        replan_count=1,
        context={"failed_agent": analyst.specification.name},
    )

    _run(
        planner.replan(
            state=state,
            context_updates={"failed_agent": analyst.specification.name},
            specifications=[analyst.specification],
        )
    )

    assert llm.prompts
    assert "Avoid agents: []" in llm.prompts[-1]


def test_registry_rejects_duplicate_agent_names() -> None:
    llm = _FakeLLMProvider()
    registry = AgentRegistry([AnalystAgent(llm_provider=llm, config=_analyst_config())])

    try:
        registry.register(AnalystAgent(llm_provider=llm, config=_analyst_config()))
    except ValueError as exc:
        assert "already registered" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("duplicate agent registration should fail")


class _BrokenAnalystAgent(BaseAgent):
    @property
    def specification(self) -> AgentSpecification:
        return AgentSpecification(
            name="broken-analyst",
            description="Broken test agent.",
            task_kinds=[AgentTaskKind.analyst],
            routing=AgentRoutingSpec(keywords=["explain"], direct_threshold=1),
            output_contract=AgentIOContract(required_keys=["answer"]),
        )

    async def execute(self, task: AgentTask):
        return self.build_result(
            task=task,
            status=AgentResultStatus.succeeded,
            output={},
        )


class _RecoveringAnalystAgent(BaseAgent):
    @property
    def specification(self) -> AgentSpecification:
        return AgentSpecification(
            name="analyst",
            description="Recovering analyst test agent.",
            task_kinds=[AgentTaskKind.analyst],
            routing=AgentRoutingSpec(keywords=["explain"], direct_threshold=1),
            output_contract=AgentIOContract(required_keys=["answer"]),
        )

    async def execute(self, task: AgentTask):
        return self.build_result(
            task=task,
            status=AgentResultStatus.succeeded,
            output={"answer": "Analyst recovered answer."},
        )


class _RevisableAnalystAgent(BaseAgent):
    def __init__(self) -> None:
        self.calls = 0
        self.contexts: list[dict[str, object]] = []

    @property
    def specification(self) -> AgentSpecification:
        return AgentSpecification(
            name="analyst",
            description="Revisable analyst test agent.",
            task_kinds=[AgentTaskKind.analyst],
            routing=AgentRoutingSpec(keywords=["revise"], direct_threshold=1),
            output_contract=AgentIOContract(required_keys=["answer"]),
        )

    async def execute(self, task: AgentTask):
        self.calls += 1
        self.contexts.append(dict(task.context))
        answer = "Initial answer."
        if task.context.get("final_review_rationale"):
            answer = "Revised answer."
        return self.build_result(
            task=task,
            status=AgentResultStatus.succeeded,
            output={"answer": answer},
        )


class _RetryableFailureAnalystAgent(BaseAgent):
    @property
    def specification(self) -> AgentSpecification:
        return AgentSpecification(
            name="analyst",
            description="Retryable failing analyst test agent.",
            task_kinds=[AgentTaskKind.analyst],
            routing=AgentRoutingSpec(keywords=["explain"], direct_threshold=1),
            output_contract=AgentIOContract(required_keys=["analysis", "result"]),
        )

    async def execute(self, task: AgentTask):
        return self.build_result(
            task=task,
            status=AgentResultStatus.failed,
            output={
                "analysis": "",
                "result": {},
                "outcome": {"recoverable": True},
            },
            error="temporary failure",
        )


class _NonRecoverableFailureAnalystAgent(BaseAgent):
    @property
    def specification(self) -> AgentSpecification:
        return AgentSpecification(
            name="analyst",
            description="Non-recoverable failing analyst test agent.",
            task_kinds=[AgentTaskKind.analyst],
            routing=AgentRoutingSpec(keywords=["explain"], direct_threshold=1),
            output_contract=AgentIOContract(required_keys=["analysis", "result"]),
        )

    async def execute(self, task: AgentTask):
        return self.build_result(
            task=task,
            status=AgentResultStatus.failed,
            output={
                "analysis": "",
                "result": {},
                "outcome": {"recoverable": False},
            },
            error="Execution failed: Binder Error: Cannot compare VARCHAR and DATE.",
        )


class _RetryContextAnalystAgent(BaseAgent):
    def __init__(self) -> None:
        self.calls = 0
        self.contexts: list[dict[str, object]] = []

    @property
    def specification(self) -> AgentSpecification:
        return AgentSpecification(
            name="analyst",
            description="Retry context test agent.",
            task_kinds=[AgentTaskKind.analyst],
            routing=AgentRoutingSpec(keywords=["explain"], direct_threshold=1),
            output_contract=AgentIOContract(required_keys=["answer"]),
        )

    async def execute(self, task: AgentTask):
        self.calls += 1
        self.contexts.append(dict(task.context))
        if self.calls == 1:
            return self.build_result(
                task=task,
                status=AgentResultStatus.failed,
                error="temporary failure",
            )
        return self.build_result(
            task=task,
            status=AgentResultStatus.succeeded,
            output={"answer": "Recovered answer."},
        )


class _OrderedAnalystAgent(BaseAgent):
    def __init__(self, *, name: str, answer: str, call_order: list[str]) -> None:
        self._name = name
        self._answer = answer
        self._call_order = call_order

    @property
    def specification(self) -> AgentSpecification:
        return AgentSpecification(
            name=self._name,
            description=f"{self._name} ordered step agent.",
            task_kinds=[AgentTaskKind.analyst],
            routing=AgentRoutingSpec(keywords=["dependency"], direct_threshold=1),
            output_contract=AgentIOContract(required_keys=["answer"]),
        )

    async def execute(self, task: AgentTask):
        self._call_order.append(self._name)
        return self.build_result(
            task=task,
            status=AgentResultStatus.succeeded,
            output={"answer": self._answer},
        )


class _StaticPlanner:
    def __init__(self, *, plan: ExecutionPlan) -> None:
        self._plan = plan

    @property
    def specification(self) -> AgentSpecification:
        return AgentSpecification(
            name="planner",
            description="Static planner for dependency tests.",
            task_kinds=[AgentTaskKind.orchestration],
            routing=AgentRoutingSpec(keywords=["plan"], direct_threshold=99),
            output_contract=AgentIOContract(required_keys=["plan"]),
            can_execute_direct=False,
        )

    async def build_plan(
        self,
        *,
        question: str,
        context: dict[str, object],
        specifications: list[AgentSpecification],
    ) -> ExecutionPlan:
        _ = (question, context, specifications)
        return self._plan

    async def replan(self, *, state, context_updates=None, specifications=None) -> ExecutionPlan:
        _ = (state, context_updates, specifications)
        return self._plan


class _PlannerShouldNotReplan:
    @property
    def specification(self) -> AgentSpecification:
        return AgentSpecification(
            name="planner",
            description="Planner that should not be called.",
            task_kinds=[AgentTaskKind.orchestration],
            routing=AgentRoutingSpec(keywords=["plan"], direct_threshold=99),
            output_contract=AgentIOContract(required_keys=["plan"]),
            can_execute_direct=False,
        )

    async def build_plan(self, *, question: str, context: dict[str, object], specifications: list[AgentSpecification]):
        raise AssertionError("planner.build_plan should not be called")

    async def replan(self, *, state, context_updates=None, specifications=None) -> ExecutionPlan:
        raise AssertionError("planner.replan should not be called for revise_answer")


def test_pev_replans_after_missing_required_output_key() -> None:
    llm = _FakeLLMProvider()
    controller = MetaControllerAgent(
        registry=AgentRegistry([_BrokenAnalystAgent(), _RecoveringAnalystAgent()]),
        llm_provider=llm,
        presentation_agent=_presentation(llm),
        max_replans=1,
    )

    run = _run(controller.handle(question="Explain this result"))

    assert run.execution_mode == "planned"
    assert run.status == "completed"
    assert run.verification[0].passed is False
    assert run.verification[0].reason_code == VerificationReasonCode.missing_output_keys
    assert run.verification[0].missing_output_keys == ["answer"]
    assert run.review_decisions[0].action == PlanReviewAction.revise_plan
    assert run.review_decisions[0].reason_code == PlanReviewReasonCode.deterministic_verification_failed
    assert run.review_decisions[-1].action == PlanReviewAction.finalize
    assert run.diagnostics["replan_count"] == 1
    assert run.final_result["answer"] == "Analyst recovered answer."


def test_meta_controller_preserves_requested_agent_mode_for_direct_analyst() -> None:
    run = _run(
        _controller().handle(
            question="Explain the current context result",
            context={
                "agent_mode": "context_analysis",
                "result": {"columns": ["region", "revenue"], "rows": [["US", 2200]]},
            },
        )
    )

    assert run.execution_mode == "direct"
    assert run.plan.steps[0].input["agent_mode"] == "context_analysis"
    assert run.status == "completed"


def test_meta_controller_normalizes_legacy_answer_mode_alias() -> None:
    llm = _AnswerAliasRouteLLMProvider()
    controller = MetaControllerAgent(
        registry=AgentRegistry([AnalystAgent(llm_provider=llm, config=_analyst_config())]),
        llm_provider=llm,
        presentation_agent=_presentation(llm),
    )

    run = _run(
        controller.handle(
            question="Explain the verified result",
            context={"result": {"columns": ["region", "revenue"], "rows": [["US", 2200]]}},
        )
    )

    assert run.execution_mode == "direct"
    assert run.status == "completed"
    assert run.plan.steps[0].input["agent_mode"] == "context_analysis"
    assert run.final_result["summary"] == "Final answer from verified outputs."


def test_meta_controller_surfaces_last_error_when_iteration_budget_exhausts() -> None:
    llm = _FakeLLMProvider()
    controller = MetaControllerAgent(
        registry=AgentRegistry([_RetryableFailureAnalystAgent()]),
        llm_provider=llm,
        presentation_agent=_presentation(llm),
        max_iterations=1,
        max_step_retries=1,
    )

    run = _run(controller.handle(question="Explain this result"))

    assert run.review_decisions[0].action == PlanReviewAction.retry_step
    assert run.review_decisions[0].reason_code == PlanReviewReasonCode.retryable_step_failure
    assert run.diagnostics["stop_reason"] == "max_iterations"
    assert run.diagnostics["terminal_error"] == "temporary failure"


def test_plan_review_does_not_retry_non_recoverable_execution_failure() -> None:
    llm = _FakeLLMProvider()
    controller = MetaControllerAgent(
        registry=AgentRegistry([_NonRecoverableFailureAnalystAgent()]),
        llm_provider=llm,
        presentation_agent=_presentation(llm),
        max_step_retries=1,
        max_replans=0,
    )

    run = _run(controller.handle(question="Explain this result"))

    assert run.review_decisions[0].action == PlanReviewAction.abort
    assert run.review_decisions[0].reason_code == PlanReviewReasonCode.verification_failed_after_replans
    assert run.diagnostics["stop_reason"] == "abort"


def test_retry_step_propagates_updated_context_to_future_execution() -> None:
    llm = _FakeLLMProvider()
    agent = _RetryContextAnalystAgent()
    controller = MetaControllerAgent(
        registry=AgentRegistry([agent]),
        llm_provider=llm,
        presentation_agent=_presentation(llm),
        max_step_retries=1,
    )

    run = _run(controller.handle(question="Explain this result"))

    assert run.status == "completed"
    assert agent.calls == 2
    assert agent.contexts[1]["last_error"] == "temporary failure"
    assert run.review_decisions[0].action == PlanReviewAction.retry_step
    assert run.review_decisions[0].reason_code == PlanReviewReasonCode.retryable_step_failure


def test_execution_honors_step_dependencies_when_plan_steps_are_out_of_order() -> None:
    llm = _FakeLLMProvider()
    call_order: list[str] = []
    prepare = _OrderedAnalystAgent(name="prepare-analyst", answer="Prepared answer.", call_order=call_order)
    finalize = _OrderedAnalystAgent(name="final-analyst", answer="Final answer.", call_order=call_order)
    plan = ExecutionPlan(
        route="planned:dependency",
        rationale="Dependency-aware execution order.",
        steps=[
            PlanStep(
                step_id="step-2",
                agent_name="final-analyst",
                task_kind=AgentTaskKind.analyst,
                question="Finalize the answer",
                expected_output=finalize.specification.output_contract,
                depends_on=["step-1"],
            ),
            PlanStep(
                step_id="step-1",
                agent_name="prepare-analyst",
                task_kind=AgentTaskKind.analyst,
                question="Prepare the answer",
                expected_output=prepare.specification.output_contract,
            ),
        ],
    )
    controller = MetaControllerAgent(
        registry=AgentRegistry([prepare, finalize]),
        llm_provider=llm,
        planner=_StaticPlanner(plan=plan),
        presentation_agent=_presentation(llm),
    )

    run = _run(controller.handle(question="Dependency ordered request"))

    assert run.execution_mode == "planned"
    assert run.status == "completed"
    assert call_order == ["prepare-analyst", "final-analyst"]
    assert [item["agent_name"] for item in run.step_results] == ["prepare-analyst", "final-analyst"]


def test_plan_review_flags_nested_empty_tabular_results_as_weak_evidence() -> None:
    step = PlanStep(
        step_id="step-1",
        agent_name="analyst",
        task_kind=AgentTaskKind.analyst,
        question="Show revenue by region",
        expected_output=AgentIOContract(required_keys=["analysis", "result"]),
    )
    result = AgentResult(
        task_id="step-1",
        agent_name="analyst",
        status=AgentResultStatus.succeeded,
        output={
            "analysis": "No rows matched the query.",
            "result": {"columns": ["region", "revenue"], "rows": []},
            "outcome": {"status": "empty_result"},
        },
    )
    verification = VerificationOutcome(
        passed=True,
        step_id="step-1",
        agent_name="analyst",
        message="Step output passed deterministic verification.",
        reason_code=VerificationReasonCode.passed,
    )
    state = PlanExecutionState(
        original_question="Show revenue by region",
        current_plan=ExecutionPlan(route="direct:analyst", steps=[step], rationale="Direct analyst"),
        max_replans=1,
    )
    state.record(step=step, result=result, verification=verification)

    decision = PlanReviewAgent().review(state)

    assert decision.action == PlanReviewAction.revise_plan
    assert decision.reason_code == PlanReviewReasonCode.weak_evidence
    assert decision.updated_context["weak_result_agent"] == "analyst"


def test_presentation_agent_returns_chart_when_tabular_data_is_chartable() -> None:
    llm = _FakeLLMProvider()
    agent = _presentation(llm)
    result = _run(
        agent.execute(
            AgentTask(
                task_id="presentation",
                task_kind=AgentTaskKind.presentation,
                question="Show a bar chart of revenue by region",
                input={"mode": "final"},
                context={
                    "step_results": [
                        {
                            "output": {
                                "result": {
                                    "columns": ["region", "revenue"],
                                    "rows": [["US", 2200], ["EMEA", 1200], ["APAC", 900]],
                                }
                            }
                        }
                    ]
                },
                expected_output=agent.specification.output_contract,
            )
        )
    )

    response = result.output["response"]
    assert response["visualization"] is not None
    assert response["visualization"]["chart_type"] == "bar"


def test_analyst_deep_research_mode_exposes_structured_sources_and_findings() -> None:
    llm = _FakeLLMProvider()
    result = _run(
        AnalystAgent(llm_provider=llm, config=_analyst_config(research_enabled=True)).execute(
            AgentTask(
                task_id="research",
                task_kind=AgentTaskKind.analyst,
                question="Research Langbridge runtime architecture",
                input={"mode": "research"},
                context={
                    "sources": [
                        {
                            "title": "Runtime architecture",
                            "url": "https://example.test/runtime",
                            "snippet": "Runtime owns semantic and federated execution.",
                        }
                    ]
                },
            )
        )
    )

    assert result.output["synthesis"].startswith("Source-backed")
    assert result.output["sources"][0]["url"] == "https://example.test/runtime"
    assert result.output["findings"][0]["source"] == "https://example.test/langbridge"
