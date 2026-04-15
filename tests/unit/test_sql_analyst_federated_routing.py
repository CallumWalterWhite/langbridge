from typing import Any

from langbridge.orchestrator.agents.analyst.agent import AnalystAgent
from langbridge.orchestrator.definitions import AnalystQueryScopePolicy
from langbridge.orchestrator.tools.sql_analyst.interfaces import (
    AnalyticalColumn,
    AnalyticalContext,
    AnalyticalDatasetBinding,
    AnalyticalField,
    AnalyticalMetric,
    AnalyticalQueryExecutionFailure,
    AnalyticalQueryExecutionResult,
    AnalystOutcomeStage,
    AnalystOutcomeStatus,
    AnalystQueryRequest,
    QueryResult,
)
from langbridge.orchestrator.tools.sql_analyst.tool import SqlAnalystTool
from langbridge.runtime.models import SqlQueryScope


class _StaticLLM:
    def __init__(self, sql: str) -> None:
        self._sql = sql

    def complete(self, prompt: str, *, temperature: float = 0.0, max_tokens: int | None = None) -> str:
        _ = (prompt, temperature, max_tokens)
        return self._sql


class _FakeQueryExecutor:
    def __init__(
        self,
        *,
        rows: list[tuple[Any, ...]] | None = None,
        failure: AnalyticalQueryExecutionFailure | None = None,
    ) -> None:
        self.calls: list[dict[str, Any]] = []
        self._rows = rows or [(1, 100)]
        self._failure = failure

    async def execute_query(
        self,
        *,
        query: str,
        query_dialect: str,
        requested_limit: int | None = None,
    ) -> AnalyticalQueryExecutionResult:
        self.calls.append(
            {
                "query": query,
                "query_dialect": query_dialect,
                "requested_limit": requested_limit,
            }
        )
        if self._failure is not None:
            raise self._failure
        return AnalyticalQueryExecutionResult(
            executable_query=query,
            result=QueryResult(
                columns=["order_id", "customer_id"],
                rows=self._rows,
                rowcount=len(self._rows),
                elapsed_ms=11,
                source_sql=query,
            ),
        )


def _semantic_context() -> AnalyticalContext:
    return AnalyticalContext(
        query_scope=SqlQueryScope.semantic,
        asset_type="semantic_model",
        asset_id="semantic-1",
        asset_name="orders_model",
        description="Governed orders model",
        datasets=[
            AnalyticalDatasetBinding(
                dataset_id="dataset-1",
                dataset_name="orders_dataset",
                sql_alias="orders",
                source_kind="connector",
                storage_kind="table",
                columns=[AnalyticalColumn(name="order_id", data_type="integer")],
            ),
            AnalyticalDatasetBinding(
                dataset_id="dataset-2",
                dataset_name="customers_dataset",
                sql_alias="customers",
                source_kind="connector",
                storage_kind="table",
                columns=[AnalyticalColumn(name="customer_id", data_type="integer")],
            ),
        ],
        tables=["orders", "customers"],
        dimensions=[
            AnalyticalField(name="order_id"),
            AnalyticalField(name="customer_id"),
        ],
        metrics=[AnalyticalMetric(name="total_orders", expression="COUNT(*)")],
        relationships=["orders.customer_id = customers.customer_id"],
    )


def _dataset_context() -> AnalyticalContext:
    return AnalyticalContext(
        query_scope=SqlQueryScope.dataset,
        asset_type="dataset",
        asset_id="dataset-1",
        asset_name="orders_dataset",
        description="Dataset-level orders context",
        datasets=[
            AnalyticalDatasetBinding(
                dataset_id="dataset-1",
                dataset_name="orders_dataset",
                sql_alias="orders",
                source_kind="connector",
                storage_kind="table",
                columns=[
                    AnalyticalColumn(name="order_id", data_type="integer"),
                    AnalyticalColumn(name="customer_id", data_type="integer"),
                ],
            )
        ],
        tables=["orders"],
        dimensions=[
            AnalyticalField(name="orders.order_id"),
            AnalyticalField(name="orders.customer_id"),
        ],
        metrics=[AnalyticalMetric(name="total_orders", expression="COUNT(*)")],
    )


def test_sql_analyst_tool_executes_semantic_model_context_through_scope_executor() -> None:
    executor = _FakeQueryExecutor()
    tool = SqlAnalystTool(
        llm=_StaticLLM("SELECT order_id, customer_id FROM orders_model ORDER BY order_id"),
        context=_semantic_context(),
        query_executor=executor,
    )

    response = tool.run(AnalystQueryRequest(question="Join orders and customers", limit=50))

    assert response.error is None
    assert response.outcome is not None
    assert response.outcome.status == AnalystOutcomeStatus.success
    assert response.asset_type == "semantic_model"
    assert response.query_scope == SqlQueryScope.semantic
    assert response.selected_semantic_model_id == "semantic-1"
    assert response.execution_mode == "federated"
    assert response.result is not None
    assert response.result.rows == [(1, 100)]
    assert len(response.selected_datasets) == 2
    assert executor.calls == [
        {
            "query": "SELECT order_id, customer_id FROM orders_model ORDER BY order_id",
            "query_dialect": "postgres",
            "requested_limit": 50,
        }
    ]


def test_sql_analyst_tool_returns_query_error_from_scope_executor() -> None:
    executor = _FakeQueryExecutor(
        failure=AnalyticalQueryExecutionFailure(
            stage=AnalystOutcomeStage.query,
            message="Semantic SQL parse failed: expected projection.",
            original_error="expected projection",
            recoverable=True,
        )
    )
    tool = SqlAnalystTool(
        llm=_StaticLLM("SELECT FROM"),
        context=_semantic_context(),
        query_executor=executor,
    )

    response = tool.run(AnalystQueryRequest(question="Break the parser"))

    assert response.error is not None
    assert response.outcome is not None
    assert response.outcome.status == AnalystOutcomeStatus.query_error
    assert "parse failed" in response.error.lower()
    assert executor.calls == [
        {
            "query": "SELECT FROM",
            "query_dialect": "postgres",
            "requested_limit": 1000,
        }
    ]


def test_sql_analyst_tool_propagates_scope_fallback_metadata() -> None:
    executor = _FakeQueryExecutor(
        failure=AnalyticalQueryExecutionFailure(
            stage=AnalystOutcomeStage.query,
            message="Semantic SQL scope does not support JOIN.",
            recoverable=False,
            metadata={"scope_fallback_eligible": True},
        )
    )
    tool = SqlAnalystTool(
        llm=_StaticLLM("SELECT order_id FROM orders_model JOIN other_model ON 1 = 1"),
        context=_semantic_context(),
        query_executor=executor,
    )

    response = tool.run(AnalystQueryRequest(question="Unsupported semantic query"))

    assert response.outcome is not None
    assert response.outcome.status == AnalystOutcomeStatus.query_error
    assert response.outcome.attempted_query_scope == SqlQueryScope.semantic
    assert response.outcome.final_query_scope == SqlQueryScope.semantic
    assert response.outcome.metadata["scope_fallback_eligible"] is True


def test_sql_analyst_tool_prompt_reinforces_strict_semantic_contract() -> None:
    tool = SqlAnalystTool(
        llm=_StaticLLM("SELECT total_orders FROM orders_model"),
        context=_semantic_context(),
        query_executor=_FakeQueryExecutor(),
    )

    prompt = tool._build_prompt(AnalystQueryRequest(question="What is the first order date?"))  # noqa: SLF001

    assert "Never invent raw SQL expressions in semantic scope." in prompt
    assert "Do not emit MIN(), MAX(), SUM(), AVG(), COUNT(), CASE" in prompt
    assert "do not approximate it with raw sql" in prompt.lower()


def test_analyst_agent_falls_back_from_semantic_to_dataset_for_unsupported_shape() -> None:
    semantic_tool = SqlAnalystTool(
        llm=_StaticLLM(
            "SELECT orders.order_id, MIN(orders.created_at) AS first_order_date FROM orders_model GROUP BY orders.order_id"
        ),
        context=_semantic_context(),
        query_executor=_FakeQueryExecutor(
            failure=AnalyticalQueryExecutionFailure(
                stage=AnalystOutcomeStage.query,
                message=(
                    "Semantic SQL scope only supports semantic member columns and "
                    "DATE_TRUNC/TIMESTAMP_TRUNC time buckets in SELECT."
                ),
                recoverable=False,
                metadata={
                    "scope_fallback_eligible": True,
                    "semantic_failure_kind": "unsupported_semantic_sql_shape",
                },
            )
        ),
        binding_name="orders",
        query_scope_policy=AnalystQueryScopePolicy.semantic_preferred,
    )
    dataset_executor = _FakeQueryExecutor(rows=[(7, 200)])
    dataset_tool = SqlAnalystTool(
        llm=_StaticLLM("SELECT orders.order_id, orders.customer_id FROM orders LIMIT 1000"),
        context=_dataset_context(),
        query_executor=dataset_executor,
        binding_name="orders",
        query_scope_policy=AnalystQueryScopePolicy.semantic_preferred,
    )
    agent = AnalystAgent(
        llm=_StaticLLM(""),
        tools=[semantic_tool, dataset_tool],
        max_retries=0,
    )

    response = agent.answer_with_request(
        AnalystQueryRequest(question="List order ids and the first order date")
    )

    assert response.error is None
    assert response.query_scope == SqlQueryScope.dataset
    assert response.result is not None
    assert response.result.rows == [(7, 200)]
    assert response.outcome is not None
    assert response.outcome.attempted_query_scope == SqlQueryScope.semantic
    assert response.outcome.final_query_scope == SqlQueryScope.dataset
    assert response.outcome.fallback_from_query_scope == SqlQueryScope.semantic
    assert response.outcome.fallback_to_query_scope == SqlQueryScope.dataset
    assert response.outcome.recovery_actions[-1].action == "fallback_query_scope"
    assert (
        response.outcome.recovery_actions[-1].details["semantic_failure_kind"]
        == "unsupported_semantic_sql_shape"
    )
    assert len(dataset_executor.calls) == 1
