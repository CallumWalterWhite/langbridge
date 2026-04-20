import asyncio

from langbridge.ai import (
    AgentIOContract,
    AgentProfile,
    AgentProfileRegistryBuilder,
    AnalystToolBundle,
    AgentRegistry,
    AgentResultStatus,
    AgentRoutingSpec,
    AgentSpecification,
    AgentTask,
    AgentTaskKind,
    BaseAgent,
    MetaControllerAgent,
    PlanReviewAction,
    WebSearchToolScope,
    LangbridgeAIFactory,
)
from langbridge.ai.agents import (
    AnalystAgent,
    AnalystAgentScope,
)
from langbridge.ai.agents.presentation import PresentationAgent
from langbridge.ai.tools.charting import ChartingTool
from langbridge.ai.tools.web_search import WebSearchPolicy, WebSearchResultItem, WebSearchTool


def _run(coro):
    return asyncio.run(coro)


class _FakeLLMProvider:
    async def acomplete(self, prompt: str, **kwargs):
        if "Choose the next execution mode" in prompt:
            if "Search current docs" in prompt:
                return '{"mode":"deep_research","reason":"web research requested"}'
            return '{"mode":"context_analysis","reason":"structured result available"}'
        if "Create a chart specification" in prompt:
            return '{"chart_type":"bar","title":"Chart","x":"region","y":"revenue"}'
        if "Synthesize source-backed research" in prompt:
            return (
                '{"synthesis":"Source-backed research synthesis.",'
                '"findings":[{"insight":"Docs found.","source":"https://docs.langbridge.dev/runtime"}],'
                '"follow_ups":[]}'
            )
        if "Compose the final Langbridge response" in prompt:
            if "Recovered answer." in prompt:
                return (
                    '{"summary":"Recovered answer.",'
                    '"result":{},"visualization":null,"research":{},'
                    '"answer":"Recovered answer.","diagnostics":{"mode":"test"}}'
                )
            return (
                '{"summary":"Profile runtime answer.",'
                '"result":{"columns":[],"rows":[]},"visualization":null,'
                '"research":{},"answer":"Profile runtime answer.","diagnostics":{"mode":"test"}}'
            )
        if "Analyze verified Langbridge result data" in prompt:
            return '{"analysis":"Scoped analyst answer.","result":{"columns":[],"rows":[]}}'
        return '{"analysis":"Analysis complete."}'

    async def create_embeddings(self, texts, embedding_model=None):
        return [[1.0] for _ in texts]


class _FakeWebSearchProvider:
    name = "fake-web"

    async def search_async(self, query: str, **kwargs):
        return [
            WebSearchResultItem(
                title="Docs",
                url="https://docs.langbridge.dev/runtime",
                snippet="Runtime docs.",
                source=self.name,
                rank=1,
            )
        ]


def _presentation(llm: _FakeLLMProvider) -> PresentationAgent:
    return PresentationAgent(llm_provider=llm, charting_tool=ChartingTool(llm_provider=llm))


def test_profile_builder_creates_profile_scoped_registries() -> None:
    commerce = AgentProfile.from_definition(
        name="commerce_analyst",
        definition={
            "features": {"deep_research_enabled": False, "visualization_enabled": True},
            "tools": [
                {
                    "name": "commerce_semantic_sql",
                    "tool_type": "sql",
                    "description": "Governed commerce semantic model.",
                    "config": {"semantic_model_ids": ["commerce_performance"]},
                }
            ],
            "access_policy": {"allowed_connectors": ["commerce_warehouse"]},
        },
    )
    growth = AgentProfile.from_definition(
        name="growth_analyst",
        definition={
            "features": {"deep_research_enabled": True, "visualization_enabled": True},
            "tools": [
                {
                    "name": "growth_analytical_sql",
                    "tool_type": "sql",
                    "description": "Growth analytics model and datasets.",
                    "config": {
                        "semantic_model_ids": ["growth_performance"],
                        "dataset_ids": ["campaign_attribution", "channel_spend_targets"],
                    },
                }
            ],
            "access_policy": {"allowed_connectors": ["growth_warehouse"]},
        },
    )

    builder = AgentProfileRegistryBuilder()
    llm = _FakeLLMProvider()
    commerce_registry = builder.build_registry(commerce, llm_provider=llm)
    growth_registry = builder.build_registry(growth, llm_provider=llm)

    commerce_names = [spec.name for spec in commerce_registry.specifications()]
    growth_names = [spec.name for spec in growth_registry.specifications()]

    assert "analyst.commerce_semantic_sql" in commerce_names
    assert "analyst.growth_analytical_sql" not in commerce_names
    assert "analyst.growth_analytical_sql" in growth_names
    growth_analyst = growth_registry.get("analyst.growth_analytical_sql")
    assert "deep_research" in growth_analyst.specification.metadata["scope"]["enabled_modes"]
    assert not any(name.startswith("deep-research.") for name in growth_names)


def test_profile_runtime_routes_to_scoped_analyst() -> None:
    profile = AgentProfile.from_definition(
        name="commerce_analyst",
        definition={
            "execution": {"max_iterations": 4},
            "tools": [
                {
                    "name": "commerce_semantic_sql",
                    "tool_type": "sql",
                    "description": "Commerce revenue and order analytics.",
                    "config": {"semantic_model_ids": ["commerce_performance"]},
                }
            ],
        },
    )
    runtime = AgentProfileRegistryBuilder().build_runtime(profile, llm_provider=_FakeLLMProvider())

    run = _run(
        runtime.meta_controller.handle(
            question="Show commerce revenue by region",
            context={"result": {"columns": [], "rows": []}},
        )
    )

    assert run.mode == "direct"
    assert run.plan.route == "direct:analyst.commerce_semantic_sql"
    assert run.step_results[0]["agent_name"] == "analyst.commerce_semantic_sql"
    assert run.step_results[0]["output"]["result"] == {"columns": [], "rows": []}


def test_ai_factory_builds_meta_controller_without_runtime_wiring() -> None:
    llm = _FakeLLMProvider()
    controller = LangbridgeAIFactory(llm_provider=llm).create_meta_controller(
        analysts=[
            AnalystToolBundle(
                scope=AnalystAgentScope(name="factory_analyst"),
            )
        ]
    )

    run = _run(
        controller.handle(
            question="Show factory result",
            context={"result": {"columns": [], "rows": []}},
        )
    )

    assert run.mode == "planned"
    assert run.step_results[0]["agent_name"] == "analyst.factory_analyst"
    assert run.final_result["summary"] == "Profile runtime answer."


def test_profile_from_shorthand_config_builds_scoped_analyst() -> None:
    profile = AgentProfile.from_config(
        {
            "name": "support_analyst",
            "description": "Support ticket analyst.",
            "semantic_model": "support_performance",
            "default": True,
        }
    )

    registry = AgentProfileRegistryBuilder().build_registry(profile, llm_provider=_FakeLLMProvider())

    assert profile.default is True
    assert [spec.name for spec in registry.specifications()] == [
        "analyst.support_analyst_sql",
    ]
    assert registry.get("analyst.support_analyst_sql").specification.metadata["scope"][
        "semantic_model_ids"
    ] == ["support_performance"]


def test_web_search_config_is_tool_scope_not_agent_scope() -> None:
    scope = WebSearchToolScope(
        name="docs_search",
        allowed_domains=["docs.langbridge.dev"],
        denied_domains=["blocked.example"],
        require_allowed_domain=True,
        focus_terms=["langbridge"],
    )

    assert "docs" in scope.routing_terms
    assert "dev" in scope.routing_terms
    assert "langbridge" in scope.routing_terms


def test_analyst_research_mode_can_use_web_search_tool_provider() -> None:
    agent = AnalystAgent(
        llm_provider=_FakeLLMProvider(),
        scope=AnalystAgentScope(
            name="docs_research",
            deep_research_enabled=True,
            web_search_enabled=True,
            web_search_focus_terms=["langbridge"],
            max_sources=3,
        ),
        web_search_tool=WebSearchTool(
            provider=_FakeWebSearchProvider(),
            policy=WebSearchPolicy(
                allowed_domains=[],
                denied_domains=[],
                focus_terms=["langbridge"],
            ),
        ),
    )

    result = _run(
        agent.execute(
            AgentTask(
                task_id="research",
                task_kind=AgentTaskKind.deep_research,
                question="Search current docs",
            )
        )
    )

    assert result.status == AgentResultStatus.succeeded
    assert result.output["sources"][0]["url"] == "https://docs.langbridge.dev/runtime"
    assert result.diagnostics["web_search"]["query"] == "Search current docs langbridge"
    assert result.diagnostics["web_search"]["provider"] == "fake-web"


def test_analyst_research_uses_only_allowed_evidence_agents() -> None:
    agent = AnalystAgent(
        llm_provider=_FakeLLMProvider(),
        scope=AnalystAgentScope(
            name="growth_research",
            deep_research_enabled=True,
            allowed_evidence_agents=["tool.web.docs_search"],
            max_sources=3,
            require_sources=True,
        )
    )

    result = _run(
        agent.execute(
            AgentTask(
                task_id="research",
                task_kind=AgentTaskKind.deep_research,
                question="Research runtime docs",
                context={
                    "step_results": [
                        {
                            "agent_name": "tool.web.docs_search",
                            "output": {
                                "results": [
                                    {
                                        "title": "Docs",
                                        "url": "https://docs.langbridge.dev/runtime",
                                        "snippet": "Runtime docs.",
                                    }
                                ]
                            },
                        },
                        {
                            "agent_name": "tool.web.general",
                            "output": {
                                "results": [
                                    {
                                        "title": "General",
                                        "url": "https://example.test/general",
                                        "snippet": "General source.",
                                    }
                                ]
                            },
                        },
                    ]
                },
            )
        )
    )

    assert result.output["sources"] == [
        {
            "title": "Docs",
            "url": "https://docs.langbridge.dev/runtime",
            "snippet": "Runtime docs.",
        }
    ]


class _FlakyAnalystAgent(BaseAgent):
    def __init__(self) -> None:
        self.calls = 0

    @property
    def specification(self) -> AgentSpecification:
        return AgentSpecification(
            name="analyst",
            description="Flaky analyst test agent.",
            task_kinds=[AgentTaskKind.analyst],
            routing=AgentRoutingSpec(keywords=["explain"], direct_threshold=1),
            output_contract=AgentIOContract(required_keys=["answer"]),
        )

    async def execute(self, task: AgentTask):
        self.calls += 1
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


def test_retry_success_reviews_latest_record() -> None:
    llm = _FakeLLMProvider()
    controller = MetaControllerAgent(
        registry=AgentRegistry([_FlakyAnalystAgent()]),
        presentation_agent=_presentation(llm),
        max_step_retries=1,
    )

    run = _run(controller.handle(question="Explain this"))

    assert [outcome.passed for outcome in run.verification] == [False, True]
    assert [decision.action for decision in run.review_decisions] == [
        PlanReviewAction.retry_step,
        PlanReviewAction.finalize,
    ]
    assert run.final_result["answer"] == "Recovered answer."
