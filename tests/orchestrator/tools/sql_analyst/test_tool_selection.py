import pathlib
import sys
import uuid

sys.path.append(str(pathlib.Path(__file__).resolve().parents[5] / "langbridge" / "langbridge"))

from langbridge.orchestrator.agents.analyst.agent import AnalystAgent
from langbridge.orchestrator.tools.sql_analyst.interfaces import (
    AnalyticalColumn,
    AnalyticalContext,
    AnalyticalDatasetBinding,
    AnalyticalMetric,
)
from langbridge.orchestrator.tools.sql_analyst.tool import SqlAnalystTool


class StaticLLM:
    def __init__(self, payload: str) -> None:
        self._payload = payload

    def complete(self, prompt: str, *, temperature: float = 0.0, max_tokens: int | None = None) -> str:
        _ = (prompt, temperature, max_tokens)
        return self._payload


class FakeFederatedExecutor:
    def __init__(self, label: str) -> None:
        self.label = label
        self.calls: list[dict[str, object]] = []

    async def execute_sql(
        self,
        *,
        sql: str,
        dialect: str,
        max_rows: int | None = None,
    ):
        self.calls.append({"sql": sql, "dialect": dialect, "max_rows": max_rows})
        from langbridge.orchestrator.tools.sql_analyst.interfaces import QueryResult

        return QueryResult(
            columns=["value"],
            rows=[(self.label,)],
            rowcount=1,
            elapsed_ms=0,
            source_sql=sql,
        )


def _dataset_context(name: str, sql_alias: str, *, tags: list[str] | None = None) -> AnalyticalContext:
    return AnalyticalContext(
        asset_type="dataset",
        asset_id=str(uuid.uuid4()),
        asset_name=name,
        description=f"{name} dataset",
        tags=tags or [],
        datasets=[
            AnalyticalDatasetBinding(
                dataset_id=str(uuid.uuid4()),
                dataset_name=name,
                sql_alias=sql_alias,
                source_kind="connector",
                storage_kind="table",
                columns=[AnalyticalColumn(name="id", data_type="integer")],
            )
        ],
        tables=[sql_alias],
    )


def _semantic_context(name: str, sql_alias: str, metric_name: str) -> AnalyticalContext:
    return AnalyticalContext(
        asset_type="semantic_model",
        asset_id=str(uuid.uuid4()),
        asset_name=name,
        description=f"{name} governed model",
        datasets=[
            AnalyticalDatasetBinding(
                dataset_id=str(uuid.uuid4()),
                dataset_name=f"{name}_dataset",
                sql_alias=sql_alias,
                source_kind="connector",
                storage_kind="table",
                columns=[AnalyticalColumn(name="id", data_type="integer")],
            )
        ],
        tables=[sql_alias],
        metrics=[AnalyticalMetric(name=metric_name, expression="COUNT(*)")],
    )


def _tool(
    context: AnalyticalContext,
    sql: str,
    label: str,
    *,
    priority: int = 0,
) -> tuple[SqlAnalystTool, FakeFederatedExecutor]:
    executor = FakeFederatedExecutor(label)
    tool = SqlAnalystTool(
        llm=StaticLLM(sql),
        context=context,
        federated_sql_executor=executor,
        priority=priority,
    )
    return tool, executor


def test_analyst_agent_selects_dataset_asset_by_keywords() -> None:
    customers_tool, customers_executor = _tool(
        _dataset_context("customers_dataset", "customers"),
        "SELECT COUNT(*) FROM customers",
        "customers",
    )
    orders_tool, orders_executor = _tool(
        _dataset_context("orders_dataset", "orders", tags=["revenue", "orders"]),
        "SELECT COUNT(*) FROM orders",
        "orders",
    )

    agent = AnalystAgent(StaticLLM(""), [customers_tool, orders_tool])
    response = agent.answer("Show revenue by orders")

    assert response.error is None
    assert response.asset_type == "dataset"
    assert response.asset_name == "orders_dataset"
    assert orders_executor.calls
    assert not customers_executor.calls


def test_analyst_agent_uses_priority_on_tie() -> None:
    tool_a, exec_a = _tool(
        _dataset_context("dataset_a", "entity_a"),
        "SELECT 1 FROM entity_a",
        "a",
        priority=1,
    )
    tool_b, exec_b = _tool(
        _dataset_context("dataset_b", "entity_b"),
        "SELECT 1 FROM entity_b",
        "b",
        priority=5,
    )

    agent = AnalystAgent(StaticLLM(""), [tool_a, tool_b])
    response = agent.answer("General question with no keywords")

    assert response.asset_name == "dataset_b"
    assert exec_b.calls
    assert not exec_a.calls


def test_analyst_agent_prefers_semantic_model_when_metric_matches() -> None:
    dataset_tool, dataset_executor = _tool(
        _dataset_context("inventory_dataset", "inventory"),
        "SELECT COUNT(*) FROM inventory",
        "inventory",
    )
    semantic_tool, semantic_executor = _tool(
        _semantic_context("kpi_model", "metrics", "retention"),
        "SELECT COUNT(*) FROM metrics",
        "metrics",
    )

    agent = AnalystAgent(StaticLLM(""), [dataset_tool, semantic_tool])
    response = agent.answer("Give me retention KPI results")

    assert response.asset_type == "semantic_model"
    assert response.asset_name == "kpi_model"
    assert semantic_executor.calls
    assert not dataset_executor.calls
