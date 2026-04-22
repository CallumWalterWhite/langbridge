import asyncio

from langbridge.ai import AgentTask, AgentTaskKind, AnalystAgentConfig
from langbridge.ai.agents import AnalystAgent
from langbridge.ai.tools.sql.interfaces import (
    AnalyticalColumn,
    AnalyticalDatasetBinding,
    AnalystExecutionOutcome,
    AnalystOutcomeStage,
    AnalystOutcomeStatus,
    AnalystQueryResponse,
    QueryResult,
    SqlQueryScope,
)
from langbridge.ai.tools.web_search import WebSearchPolicy, WebSearchResultItem, WebSearchTool


def _run(coro):
    return asyncio.run(coro)


class _FakeLLMProvider:
    async def acomplete(self, prompt: str, **kwargs):
        if "Choose the single best SQL analysis tool" in prompt:
            if '"name": "dataset-orders"' in prompt and '"name": "semantic-orders"' not in prompt:
                return '{"tool_name":"dataset-orders","reason":"Fallback to dataset scope."}'
            return '{"tool_name":"semantic-orders","reason":"Prefer governed semantic scope first."}'
        if "Review governed SQL evidence for a Langbridge analyst workflow" in prompt:
            if "Show current order trend sources" in prompt:
                return (
                    '{"decision":"augment_with_web","reason":"Need current external context.",'
                    '"sufficiency":"partial"}'
                )
            if "Show order trend" in prompt:
                return (
                    '{"decision":"clarify","reason":"Need a tighter filter.",'
                    '"sufficiency":"insufficient",'
                    '"clarification_question":"Which filters, entity, or time period should I use to refine the analysis?"}'
                )
            return '{"decision":"answer","reason":"Governed SQL is sufficient.","sufficiency":"sufficient"}'
        if "Synthesize a final analytical answer for a Langbridge user from governed SQL analysis" in prompt:
            return (
                '{"analysis":"Final answer using governed data and external sources.",'
                '"findings":[{"insight":"Current external context found.","source":"https://example.test/orders"}],'
                '"follow_ups":[]}'
            )
        if "Synthesize source-backed research" in prompt:
            return (
                '{"synthesis":"Evidence synthesis using governed and source evidence.",'
                '"findings":[{"insight":"Governed orders evidence used.","source":"governed_result"}],'
                '"follow_ups":[]}'
            )
        if "Summarize verified SQL analysis" in prompt:
            return '{"analysis":"Fallback answer from dataset-native SQL."}'
        raise AssertionError(prompt)


class _AlternativeGovernedLLMProvider(_FakeLLMProvider):
    async def acomplete(self, prompt: str, **kwargs):
        if "Choose the single best SQL analysis tool" in prompt:
            if '"name": "dataset-orders"' in prompt and '"name": "semantic-orders"' in prompt:
                return '{"tool_name":"dataset-orders","reason":"Try dataset scope first."}'
            if '"name": "semantic-orders"' in prompt:
                return '{"tool_name":"semantic-orders","reason":"Retry with semantic scope."}'
        if "Review governed SQL evidence for a Langbridge analyst workflow" in prompt:
            if '"rows": []' in prompt:
                return (
                    '{"decision":"clarify","reason":"Dataset scope returned no matching rows.",'
                    '"sufficiency":"insufficient",'
                    '"clarification_question":"Which filters, entity, or time period should I use to refine the analysis?"}'
                )
            return '{"decision":"answer","reason":"Semantic scope answered the question.","sufficiency":"sufficient"}'
        return await super().acomplete(prompt, **kwargs)


class _FakeWebSearchProvider:
    name = "fake-web"

    async def search_async(self, query: str, **kwargs):
        _ = (query, kwargs)
        return [
            WebSearchResultItem(
                title="Orders source",
                url="https://example.test/orders",
                snippet="Current orders context.",
                source=self.name,
                rank=1,
            )
        ]


class _FakeSqlTool:
    def __init__(self, *, name: str, asset_type: str, query_scope: SqlQueryScope, response: AnalystQueryResponse):
        self.name = name
        self.description = f"{name} description"
        self.asset_type = asset_type
        self.query_scope = query_scope
        self._response = response
        self.calls = 0

    def describe(self) -> dict[str, object]:
        return {
            "name": self.name,
            "description": self.description,
            "asset_type": self.asset_type,
            "asset_id": self._response.asset_id,
            "asset_name": self._response.asset_name,
            "query_scope": self.query_scope.value,
            "datasets": [],
            "tables": [],
            "dimensions": [],
            "measures": [],
            "metrics": [],
        }

    async def arun(self, request):
        _ = request
        self.calls += 1
        return self._response


def _dataset_binding() -> AnalyticalDatasetBinding:
    return AnalyticalDatasetBinding(
        dataset_id="orders",
        dataset_name="Orders",
        sql_alias="orders",
        columns=[AnalyticalColumn(name="month", data_type="date"), AnalyticalColumn(name="orders", data_type="integer")],
    )


def _semantic_failure_response() -> AnalystQueryResponse:
    return AnalystQueryResponse(
        analysis_path="semantic_model",
        query_scope=SqlQueryScope.semantic,
        execution_mode="federated",
        asset_type="semantic_model",
        asset_id="commerce",
        asset_name="commerce",
        selected_semantic_model_id="commerce",
        sql_canonical="SELECT unsupported_shape FROM commerce",
        sql_executable="SELECT unsupported_shape FROM commerce",
        dialect="postgres",
        selected_datasets=[_dataset_binding()],
        result=None,
        error="Semantic SQL scope does not support requested query shape.",
        outcome=AnalystExecutionOutcome(
            status=AnalystOutcomeStatus.query_error,
            stage=AnalystOutcomeStage.query,
            message="Semantic SQL scope does not support requested query shape.",
            original_error="unsupported semantic query shape",
            recoverable=False,
            terminal=False,
            metadata={
                "scope_fallback_eligible": True,
                "semantic_failure_kind": "unsupported_semantic_sql_shape",
            },
        ),
    )


def _dataset_success_response() -> AnalystQueryResponse:
    return AnalystQueryResponse(
        analysis_path="dataset",
        query_scope=SqlQueryScope.dataset,
        execution_mode="federated",
        asset_type="dataset",
        asset_id="orders",
        asset_name="Orders",
        sql_canonical="SELECT month, COUNT(*) AS orders FROM orders GROUP BY month",
        sql_executable="SELECT month, COUNT(*) AS orders FROM orders GROUP BY month",
        dialect="postgres",
        selected_datasets=[_dataset_binding()],
        result=QueryResult(columns=["month", "orders"], rows=[("2026-01-01", 12)], rowcount=1),
        outcome=AnalystExecutionOutcome(
            status=AnalystOutcomeStatus.success,
            stage=AnalystOutcomeStage.result,
            recoverable=False,
            terminal=True,
        ),
    )


def _semantic_success_response() -> AnalystQueryResponse:
    return AnalystQueryResponse(
        analysis_path="semantic_model",
        query_scope=SqlQueryScope.semantic,
        execution_mode="federated",
        asset_type="semantic_model",
        asset_id="commerce",
        asset_name="commerce",
        selected_semantic_model_id="commerce",
        sql_canonical="SELECT month, COUNT(*) AS orders FROM commerce GROUP BY month",
        sql_executable="SELECT month, COUNT(*) AS orders FROM commerce GROUP BY month",
        dialect="postgres",
        selected_datasets=[_dataset_binding()],
        result=QueryResult(columns=["month", "orders"], rows=[("2026-01-01", 12)], rowcount=1),
        outcome=AnalystExecutionOutcome(
            status=AnalystOutcomeStatus.success,
            stage=AnalystOutcomeStage.result,
            recoverable=False,
            terminal=True,
            attempted_query_scope=SqlQueryScope.semantic,
            final_query_scope=SqlQueryScope.semantic,
            selected_semantic_model_id="commerce",
            selected_dataset_ids=["orders"],
        ),
    )


def _empty_dataset_response() -> AnalystQueryResponse:
    return AnalystQueryResponse(
        analysis_path="dataset",
        query_scope=SqlQueryScope.dataset,
        execution_mode="federated",
        asset_type="dataset",
        asset_id="orders",
        asset_name="Orders",
        sql_canonical="SELECT month, COUNT(*) AS orders FROM orders GROUP BY month",
        sql_executable="SELECT month, COUNT(*) AS orders FROM orders GROUP BY month",
        dialect="postgres",
        selected_datasets=[_dataset_binding()],
        result=QueryResult(columns=["month", "orders"], rows=[], rowcount=0),
        outcome=AnalystExecutionOutcome(
            status=AnalystOutcomeStatus.empty_result,
            stage=AnalystOutcomeStage.result,
            message="No rows matched the query.",
            recoverable=False,
            terminal=True,
        ),
    )


def test_analyst_falls_back_from_semantic_to_dataset_scope() -> None:
    agent = AnalystAgent(
        llm_provider=_FakeLLMProvider(),
        config=AnalystAgentConfig.model_validate(
            {
                "name": "commerce",
                "analyst_scope": {
                    "semantic_models": ["commerce"],
                    "datasets": ["orders"],
                    "query_policy": "semantic_preferred",
                },
            }
        ),
        sql_analysis_tools=[
            _FakeSqlTool(
                name="semantic-orders",
                asset_type="semantic_model",
                query_scope=SqlQueryScope.semantic,
                response=_semantic_failure_response(),
            ),
            _FakeSqlTool(
                name="dataset-orders",
                asset_type="dataset",
                query_scope=SqlQueryScope.dataset,
                response=_dataset_success_response(),
            ),
        ],
    )

    result = _run(
        agent.execute(
            AgentTask(
                task_id="analyst-fallback",
                task_kind=AgentTaskKind.analyst,
                question="Show first order date by month",
                input={"mode": "sql"},
            )
        )
    )

    assert result.status.value == "succeeded"
    assert result.diagnostics["fallback"]["from_scope"] == "semantic"
    assert result.diagnostics["fallback"]["to_scope"] == "dataset"
    assert result.output["query_scope"] == "dataset"
    assert result.output["error_taxonomy"]["kind"] == "unsupported_semantic_sql_shape"
    assert result.output["outcome"]["attempted_query_scope"] == "semantic"
    assert result.output["outcome"]["final_query_scope"] == "dataset"
    assert result.output["outcome"]["fallback_to_query_scope"] == "dataset"
    assert result.output["outcome"]["recovery_actions"][-1]["action"] == "fallback_query_scope"


def test_analyst_sql_can_augment_with_web_sources() -> None:
    agent = AnalystAgent(
        llm_provider=_FakeLLMProvider(),
        config=AnalystAgentConfig.model_validate(
            {
                "name": "commerce",
                "analyst_scope": {
                    "semantic_models": ["commerce"],
                    "datasets": ["orders"],
                    "query_policy": "dataset_preferred",
                },
                "research_scope": {"enabled": True},
                "web_search_scope": {"enabled": True},
            }
        ),
        sql_analysis_tools=[
            _FakeSqlTool(
                name="dataset-orders",
                asset_type="dataset",
                query_scope=SqlQueryScope.dataset,
                response=_dataset_success_response(),
            )
        ],
        web_search_tool=WebSearchTool(
            provider=_FakeWebSearchProvider(),
            policy=WebSearchPolicy(allowed_domains=[], denied_domains=[]),
        ),
    )

    result = _run(
        agent.execute(
            AgentTask(
                task_id="analyst-augment-web",
                task_kind=AgentTaskKind.analyst,
                question="Show current order trend sources",
                input={"mode": "sql"},
            )
        )
    )

    assert result.status.value == "succeeded"
    assert result.output["analysis"] == "Final answer using governed data and external sources."
    assert result.output["sources"][0]["url"] == "https://example.test/orders"
    assert result.output["evidence"]["assessment"]["decision"] == "augment_with_web"
    assert result.output["evidence"]["external"]["used"] is True
    assert result.output["review_hints"]["evidence_review_decision"] == "augment_with_web"
    assert result.output["review_hints"]["external_augmentation_used"] is True
    assert result.diagnostics["web_search"]["provider"] == "fake-web"


def test_analyst_sql_respects_external_augmentation_budget() -> None:
    agent = AnalystAgent(
        llm_provider=_FakeLLMProvider(),
        config=AnalystAgentConfig.model_validate(
            {
                "name": "commerce",
                "analyst_scope": {
                    "semantic_models": ["commerce"],
                    "datasets": ["orders"],
                    "query_policy": "dataset_preferred",
                },
                "research_scope": {"enabled": True},
                "web_search_scope": {"enabled": True},
                "execution": {"max_external_augmentations": 0},
            }
        ),
        sql_analysis_tools=[
            _FakeSqlTool(
                name="dataset-orders",
                asset_type="dataset",
                query_scope=SqlQueryScope.dataset,
                response=_dataset_success_response(),
            )
        ],
        web_search_tool=WebSearchTool(
            provider=_FakeWebSearchProvider(),
            policy=WebSearchPolicy(allowed_domains=[], denied_domains=[]),
        ),
    )

    result = _run(
        agent.execute(
            AgentTask(
                task_id="analyst-augment-budget",
                task_kind=AgentTaskKind.analyst,
                question="Show current order trend sources",
                input={"mode": "sql"},
            )
        )
    )

    assert result.status.value == "succeeded"
    assert result.output["analysis"] == "Fallback answer from dataset-native SQL."
    assert result.output["sources"] == []
    assert result.output["evidence"]["external"]["used"] is False
    assert result.output["review_hints"]["external_augmentation_used"] is False
    assert result.output["review_hints"]["evidence_review_decision"] == "augment_with_web"
    assert result.diagnostics["web_search"] is None


def test_analyst_sql_empty_result_marks_weak_evidence() -> None:
    agent = AnalystAgent(
        llm_provider=_FakeLLMProvider(),
        config=AnalystAgentConfig.model_validate(
            {
                "name": "commerce",
                "analyst_scope": {
                    "semantic_models": ["commerce"],
                    "datasets": ["orders"],
                    "query_policy": "dataset_preferred",
                },
            }
        ),
        sql_analysis_tools=[
            _FakeSqlTool(
                name="dataset-orders",
                asset_type="dataset",
                query_scope=SqlQueryScope.dataset,
                response=_empty_dataset_response(),
            )
        ],
    )

    result = _run(
        agent.execute(
            AgentTask(
                task_id="analyst-empty-result",
                task_kind=AgentTaskKind.analyst,
                question="Show order trend",
                input={"mode": "sql"},
            )
        )
    )

    assert result.status.value == "needs_clarification"
    assert result.error == "Which filters, entity, or time period should I use to refine the analysis?"
    assert result.diagnostics["weak_evidence"] is True
    assert result.diagnostics["evidence_review"]["decision"] == "clarify"
    assert result.output["evidence"]["governed"]["answered_question"] is False
    assert result.output["evidence"]["assessment"]["decision"] == "clarify"
    assert result.output["review_hints"]["governed_empty_result"] is True


def test_analyst_sql_retries_with_alternative_governed_tool_before_clarifying() -> None:
    dataset_tool = _FakeSqlTool(
        name="dataset-orders",
        asset_type="dataset",
        query_scope=SqlQueryScope.dataset,
        response=_empty_dataset_response(),
    )
    semantic_tool = _FakeSqlTool(
        name="semantic-orders",
        asset_type="semantic_model",
        query_scope=SqlQueryScope.semantic,
        response=_semantic_success_response(),
    )
    agent = AnalystAgent(
        llm_provider=_AlternativeGovernedLLMProvider(),
        config=AnalystAgentConfig.model_validate(
            {
                "name": "commerce",
                "analyst_scope": {
                    "semantic_models": ["commerce"],
                    "datasets": ["orders"],
                    "query_policy": "dataset_preferred",
                },
                "execution": {
                    "max_governed_attempts": 2,
                    "max_evidence_rounds": 2,
                },
            }
        ),
        sql_analysis_tools=[dataset_tool, semantic_tool],
    )

    result = _run(
        agent.execute(
            AgentTask(
                task_id="analyst-governed-retry",
                task_kind=AgentTaskKind.analyst,
                question="Show order trend with governed retry",
                input={"mode": "sql"},
            )
        )
    )

    assert result.status.value == "succeeded"
    assert dataset_tool.calls == 1
    assert semantic_tool.calls == 1
    assert result.output["query_scope"] == "semantic"
    assert result.output["evidence"]["governed"]["attempt_count"] == 2
    assert result.output["evidence"]["governed"]["tools_tried"] == ["dataset-orders", "semantic-orders"]
    assert result.diagnostics["governed_attempt_count"] == 2
    assert result.diagnostics["governed_tools_tried"] == ["dataset-orders", "semantic-orders"]


def test_analyst_sql_respects_governed_attempt_budget_before_clarifying() -> None:
    dataset_tool = _FakeSqlTool(
        name="dataset-orders",
        asset_type="dataset",
        query_scope=SqlQueryScope.dataset,
        response=_empty_dataset_response(),
    )
    semantic_tool = _FakeSqlTool(
        name="semantic-orders",
        asset_type="semantic_model",
        query_scope=SqlQueryScope.semantic,
        response=_semantic_success_response(),
    )
    agent = AnalystAgent(
        llm_provider=_AlternativeGovernedLLMProvider(),
        config=AnalystAgentConfig.model_validate(
            {
                "name": "commerce",
                "analyst_scope": {
                    "semantic_models": ["commerce"],
                    "datasets": ["orders"],
                    "query_policy": "dataset_preferred",
                },
                "execution": {
                    "max_governed_attempts": 2,
                    "max_evidence_rounds": 1,
                },
            }
        ),
        sql_analysis_tools=[dataset_tool, semantic_tool],
    )

    result = _run(
        agent.execute(
            AgentTask(
                task_id="analyst-governed-budget",
                task_kind=AgentTaskKind.analyst,
                question="Show order trend with governed retry",
                input={"mode": "sql"},
            )
        )
    )

    assert result.status.value == "needs_clarification"
    assert dataset_tool.calls == 1
    assert semantic_tool.calls == 0
    assert result.output["evidence"]["governed"]["attempt_count"] == 1
    assert result.diagnostics["governed_attempt_count"] == 1


def test_analyst_research_mode_uses_governed_seed_before_external_sources() -> None:
    dataset_tool = _FakeSqlTool(
        name="dataset-orders",
        asset_type="dataset",
        query_scope=SqlQueryScope.dataset,
        response=_dataset_success_response(),
    )
    agent = AnalystAgent(
        llm_provider=_FakeLLMProvider(),
        config=AnalystAgentConfig.model_validate(
            {
                "name": "commerce",
                "analyst_scope": {
                    "semantic_models": ["commerce"],
                    "datasets": ["orders"],
                    "query_policy": "dataset_preferred",
                },
                "research_scope": {"enabled": True, "max_sources": 3},
                "web_search_scope": {"enabled": True},
            }
        ),
        sql_analysis_tools=[dataset_tool],
    )

    result = _run(
        agent.execute(
            AgentTask(
                task_id="analyst-research-governed-seed",
                task_kind=AgentTaskKind.analyst,
                question="Research order trend evidence",
                input={"mode": "research"},
                context={
                    "sources": [
                        {
                            "title": "Orders source",
                            "url": "https://example.test/orders",
                            "snippet": "Current orders context.",
                        }
                    ]
                },
            )
        )
    )

    assert result.status.value == "succeeded"
    assert dataset_tool.calls == 1
    assert result.output["synthesis"] == "Evidence synthesis using governed and source evidence."
    assert result.output["result"]["rows"] == [["2026-01-01", 12]]
    assert result.output["sources"][0]["url"] == "https://example.test/orders"
    assert result.output["evidence"]["governed"]["attempted"] is True
    assert result.output["evidence"]["governed"]["attempt_count"] == 1
    assert result.output["findings"][0]["source"] == "governed_result"
    assert result.diagnostics["governed_seeded"] is True
    assert result.diagnostics["governed_attempt_count"] == 1


def test_analyst_research_mode_allows_governed_only_evidence_when_sources_required() -> None:
    dataset_tool = _FakeSqlTool(
        name="dataset-orders",
        asset_type="dataset",
        query_scope=SqlQueryScope.dataset,
        response=_dataset_success_response(),
    )
    agent = AnalystAgent(
        llm_provider=_FakeLLMProvider(),
        config=AnalystAgentConfig.model_validate(
            {
                "name": "commerce",
                "analyst_scope": {
                    "semantic_models": ["commerce"],
                    "datasets": ["orders"],
                    "query_policy": "dataset_preferred",
                },
                "research_scope": {"enabled": True, "require_sources": True},
            }
        ),
        sql_analysis_tools=[dataset_tool],
    )

    result = _run(
        agent.execute(
            AgentTask(
                task_id="analyst-research-governed-only",
                task_kind=AgentTaskKind.analyst,
                question="Research order trend evidence",
                input={"mode": "research"},
            )
        )
    )

    assert result.status.value == "succeeded"
    assert dataset_tool.calls == 1
    assert result.output["sources"] == []
    assert result.output["synthesis"] == "Evidence synthesis using governed and source evidence."
    assert result.output["result"]["rows"] == [["2026-01-01", 12]]
    assert result.output["evidence"]["governed"]["attempted"] is True
    assert result.output["evidence"]["governed"]["attempt_count"] == 1
    assert result.output["evidence"]["external"]["used"] is False
    assert result.diagnostics["weak_evidence"] is False
    assert result.diagnostics["governed_seeded"] is True
