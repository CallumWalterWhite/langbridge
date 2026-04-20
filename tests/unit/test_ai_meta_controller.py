import asyncio

from langbridge.ai import (
    AgentIOContract,
    AgentRegistry,
    AgentResultStatus,
    AgentRoutingSpec,
    AgentSpecification,
    AgentTask,
    AgentTaskKind,
    BaseAgent,
    MetaControllerAgent,
    PlanReviewAction,
)
from langbridge.ai.agents import (
    AnalystAgent,
    AnalystAgentScope,
    PresentationAgent,
)
from langbridge.ai.tools.charting import ChartingTool
from langbridge.ai.tools.web_search import WebSearchResultItem, WebSearchTool


def _run(coro):
    return asyncio.run(coro)


class _FakeLLMProvider:
    async def acomplete(self, prompt: str, **kwargs):
        if "Choose the next execution mode" in prompt:
            if "Search the web" in prompt:
                return '{"mode":"deep_research","reason":"web research requested"}'
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


def _presentation(llm: _FakeLLMProvider) -> PresentationAgent:
    return PresentationAgent(llm_provider=llm, charting_tool=ChartingTool(llm_provider=llm))


def _controller() -> MetaControllerAgent:
    llm = _FakeLLMProvider()
    registry = AgentRegistry(
        [
            AnalystAgent(
                llm_provider=llm,
                scope=AnalystAgentScope(
                    deep_research_enabled=True,
                    web_search_enabled=True,
                    web_search_focus_terms=["langbridge"],
                ),
                web_search_tool=WebSearchTool(provider=_FakeWebSearchProvider()),
            ),
        ]
    )
    return MetaControllerAgent(registry=registry, presentation_agent=_presentation(llm))


def test_meta_controller_routes_simple_analyst_question_directly() -> None:
    run = _run(
        _controller().handle(
            question="Show revenue by region",
            context={"semantic_model_id": "commerce", "result": {"columns": [], "rows": []}},
        )
    )

    assert run.mode == "direct"
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

    assert run.mode == "planned"
    assert [step.agent_name for step in run.plan.steps] == [
        "analyst",
    ]
    assert run.plan.steps[0].task_kind == AgentTaskKind.deep_research
    assert all(item.passed for item in run.verification)
    assert run.final_result["research"]["synthesis"].startswith("Source-backed")


def test_registry_rejects_duplicate_agent_names() -> None:
    llm = _FakeLLMProvider()
    registry = AgentRegistry([AnalystAgent(llm_provider=llm)])

    try:
        registry.register(AnalystAgent(llm_provider=llm))
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


def test_pev_replans_after_missing_required_output_key() -> None:
    llm = _FakeLLMProvider()
    controller = MetaControllerAgent(
        registry=AgentRegistry([_BrokenAnalystAgent(), _RecoveringAnalystAgent()]),
        presentation_agent=_presentation(llm),
        max_replans=1,
    )

    run = _run(controller.handle(question="Explain this result"))

    assert run.mode == "direct"
    assert run.verification[0].passed is False
    assert run.verification[0].missing_output_keys == ["answer"]
    assert run.review_decisions[0].action == PlanReviewAction.revise_plan
    assert run.review_decisions[-1].action == PlanReviewAction.finalize
    assert run.diagnostics["replan_count"] == 1
    assert run.final_result["answer"] == "Analyst recovered answer."


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
        AnalystAgent(llm_provider=llm, scope=AnalystAgentScope(deep_research_enabled=True)).execute(
            AgentTask(
                task_id="research",
                task_kind=AgentTaskKind.deep_research,
                question="Research Langbridge runtime architecture",
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
