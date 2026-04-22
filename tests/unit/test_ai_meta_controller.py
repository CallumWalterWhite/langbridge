import asyncio

from langbridge.ai import (
    AgentIOContract,
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
)
from langbridge.ai.agents import (
    AnalystAgent,
    PresentationAgent,
)
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
                    '{"action":"plan","rationale":"External source-backed synthesis needs a plan.",'
                    '"agent_name":null,"task_kind":null,"input":{},'
                    '"clarification_question":null,'
                    '"plan_guidance":"Use source-backed deep research."}'
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
    assert all(item.passed for item in run.verification)
    assert run.review_decisions[-1].action == PlanReviewAction.finalize
    assert run.final_result["summary"] == "Final answer from verified outputs."
    assert run.final_result["visualization"] is None


def test_meta_controller_uses_planner_for_web_research() -> None:
    run = _run(
        _controller().handle(
            question="Search the web and then explain latest sources for Langbridge"
        )
    )

    assert run.execution_mode == "planned"
    assert run.status == "completed"
    assert [step.agent_name for step in run.plan.steps] == [
        "analyst",
    ]
    assert run.plan.steps[0].task_kind == AgentTaskKind.analyst
    assert run.plan.steps[0].input["agent_mode"] == "research"
    assert "mode" not in run.plan.steps[0].input
    assert all(item.passed for item in run.verification)
    assert run.final_result["research"]["synthesis"].startswith("Source-backed")


def test_meta_controller_can_ask_clarification_before_execution() -> None:
    run = _run(_controller().handle(question="Show it"))

    assert run.execution_mode is None
    assert run.status == "clarification_needed"
    assert run.plan.route == "clarification"
    assert run.verification == []
    assert run.final_result["answer"] == "Which metric and dataset should I use?"
    assert run.diagnostics["stop_reason"] == "clarification"


def test_planner_can_return_clarification_instead_of_empty_plan_failure() -> None:
    run = _run(_controller().handle(question="Ambiguous planned request"))

    assert run.execution_mode == "planned"
    assert run.status == "clarification_needed"
    assert run.plan.route == "planned:clarification"
    assert run.final_result["answer"] == "Which metric and dataset should I use?"
    assert run.diagnostics["clarification_source"] == "planner"


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
    assert run.verification[0].missing_output_keys == ["answer"]
    assert run.review_decisions[0].action == PlanReviewAction.revise_plan
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
    assert run.diagnostics["stop_reason"] == "abort"


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
