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


def _run(coro):
    return asyncio.run(coro)


class _FakeLLMProvider:
    async def acomplete(self, prompt: str, **kwargs):
        if "Choose the single best SQL analysis tool" in prompt:
            if '"name": "dataset-orders"' in prompt and '"name": "semantic-orders"' not in prompt:
                return '{"tool_name":"dataset-orders","reason":"Fallback to dataset scope."}'
            return '{"tool_name":"semantic-orders","reason":"Prefer governed semantic scope first."}'
        if "Summarize verified SQL analysis" in prompt:
            return '{"analysis":"Fallback answer from dataset-native SQL."}'
        raise AssertionError(prompt)


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
