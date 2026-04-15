import pathlib
import sys
import uuid
from typing import Any

sys.path.append(str(pathlib.Path(__file__).resolve().parents[5] / "langbridge" / "langbridge"))

from langbridge.orchestrator.tools.sql_analyst.interfaces import (
    AnalyticalColumn,
    AnalyticalContext,
    AnalyticalDatasetBinding,
    AnalyticalQueryExecutionResult,
    AnalystOutcomeStatus,
    AnalystQueryRequest,
    QueryResult,
)
from langbridge.orchestrator.tools.sql_analyst.tool import SqlAnalystTool
from langbridge.runtime.models import SqlQueryScope
from langbridge.runtime.services.semantic_vector_search_service import (
    SemanticVectorSearchHit,
)


class DummyLLM:
    def __init__(self, sql: str) -> None:
        self._sql = sql
        self.prompts: list[str] = []

    def complete(self, prompt: str, *, temperature: float = 0.0, max_tokens: int | None = None) -> str:
        _ = (temperature, max_tokens)
        self.prompts.append(prompt)
        return self._sql


class RecordingQueryExecutor:
    def __init__(
        self,
        *,
        rows: list[tuple[Any, ...]] | None = None,
        apply_limit: bool = True,
    ) -> None:
        self.calls: list[dict[str, Any]] = []
        self._rows = rows or [(42,)]
        self._apply_limit = apply_limit

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
        executable_query = query
        if self._apply_limit and requested_limit is not None:
            executable_query = f"{query} LIMIT {requested_limit}"
        return AnalyticalQueryExecutionResult(
            executable_query=executable_query,
            result=QueryResult(
                columns=["value"],
                rows=self._rows,
                rowcount=len(self._rows),
                elapsed_ms=5,
                source_sql=executable_query,
            ),
        )


def _dataset_context() -> AnalyticalContext:
    return AnalyticalContext(
        query_scope=SqlQueryScope.dataset,
        asset_type="dataset",
        asset_id="dataset-1",
        asset_name="orders_dataset",
        description="Orders dataset",
        datasets=[
            AnalyticalDatasetBinding(
                dataset_id="dataset-1",
                dataset_name="orders_dataset",
                sql_alias="orders",
                source_kind="connector",
                storage_kind="table",
                columns=[
                    AnalyticalColumn(name="order_id", data_type="integer"),
                    AnalyticalColumn(name="amount", data_type="decimal"),
                ],
            )
        ],
        tables=["orders"],
    )


def _semantic_context() -> AnalyticalContext:
    return AnalyticalContext(
        query_scope=SqlQueryScope.semantic,
        asset_type="semantic_model",
        asset_id="semantic-model-1",
        asset_name="orders_semantic",
        description="Orders semantic model",
        datasets=[
            AnalyticalDatasetBinding(
                dataset_id="dataset-1",
                dataset_name="orders_dataset",
                sql_alias="shopify_orders",
                source_kind="connector",
                storage_kind="table",
                columns=[
                    AnalyticalColumn(name="country", data_type="text"),
                    AnalyticalColumn(name="amount", data_type="decimal"),
                ],
            )
        ],
        tables=["shopify_orders"],
    )


class DummyEmbedder:
    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]


class RecordingSemanticVectorSearchService:
    def __init__(self, hits: list[SemanticVectorSearchHit]) -> None:
        self._hits = hits
        self.calls: list[dict[str, Any]] = []

    async def search(
        self,
        *,
        workspace_id,
        semantic_model_id,
        queries,
        embedding_provider=None,
        top_k=5,
    ) -> list[SemanticVectorSearchHit]:
        self.calls.append(
            {
                "workspace_id": workspace_id,
                "semantic_model_id": semantic_model_id,
                "queries": list(queries),
                "embedding_provider": embedding_provider,
                "top_k": top_k,
            }
        )
        return list(self._hits)


def test_sql_analyst_tool_executes_dataset_scope_through_query_executor() -> None:
    llm = DummyLLM("SELECT COUNT(*) AS order_count FROM orders")
    executor = RecordingQueryExecutor(rows=[(2,)])
    tool = SqlAnalystTool(
        llm=llm,
        context=_dataset_context(),
        query_executor=executor,
    )

    response = tool.run(AnalystQueryRequest(question="How many orders?"))

    assert response.error is None
    assert response.query_scope == SqlQueryScope.dataset
    assert response.outcome is not None
    assert response.outcome.status == AnalystOutcomeStatus.success
    assert response.outcome.final_query_scope == SqlQueryScope.dataset
    assert response.analysis_path == "dataset"
    assert response.execution_mode == "federated"
    assert response.asset_name == "orders_dataset"
    assert response.sql_canonical == "SELECT COUNT(*) AS order_count FROM orders"
    assert response.sql_executable == "SELECT COUNT(*) AS order_count FROM orders LIMIT 1000"
    assert executor.calls == [
        {
            "query": "SELECT COUNT(*) AS order_count FROM orders",
            "query_dialect": "postgres",
            "requested_limit": 1000,
        }
    ]
    assert response.result == QueryResult(
        columns=["value"],
        rows=[(2,)],
        rowcount=1,
        elapsed_ms=5,
        source_sql="SELECT COUNT(*) AS order_count FROM orders LIMIT 1000",
    )


def test_sql_analyst_tool_passes_requested_limit_to_dataset_executor() -> None:
    llm = DummyLLM("SELECT order_id FROM orders")
    executor = RecordingQueryExecutor()
    tool = SqlAnalystTool(
        llm=llm,
        context=_dataset_context(),
        query_executor=executor,
    )

    response = tool.run(AnalystQueryRequest(question="List orders", limit=10))

    assert response.error is None
    assert response.outcome is not None
    assert response.outcome.status == AnalystOutcomeStatus.success
    assert response.sql_executable == "SELECT order_id FROM orders LIMIT 10"
    assert executor.calls[0]["requested_limit"] == 10


def test_sql_analyst_tool_uses_semantic_first_prompting_and_vector_hints() -> None:
    llm = DummyLLM(
        "SELECT country, COUNT(*) AS order_count "
        "FROM orders_semantic "
        "WHERE country = 'France' "
        "GROUP BY country"
    )
    executor = RecordingQueryExecutor(rows=[(12,)], apply_limit=False)
    workspace_id = uuid.uuid4()
    semantic_model_id = uuid.uuid4()
    semantic_search = RecordingSemanticVectorSearchService(
        [
            SemanticVectorSearchHit(
                index_id=uuid.uuid4(),
                semantic_model_id=semantic_model_id,
                dataset_key="shopify_orders",
                dimension_name="country",
                matched_value="France",
                score=0.97,
                source_text="French market",
            )
        ]
    )
    tool = SqlAnalystTool(
        llm=llm,
        context=_semantic_context(),
        query_executor=executor,
        embedder=DummyEmbedder(),
        semantic_vector_search_service=semantic_search,
        semantic_vector_search_workspace_id=workspace_id,
        semantic_vector_search_model_id=semantic_model_id,
    )

    response = tool.run(AnalystQueryRequest(question="How many orders came from the French market?"))

    assert response.error is None
    assert response.query_scope == SqlQueryScope.semantic
    assert response.selected_semantic_model_id == "semantic-model-1"
    assert response.outcome is not None
    assert response.outcome.status == AnalystOutcomeStatus.success
    assert response.outcome.final_query_scope == SqlQueryScope.semantic
    assert semantic_search.calls == [
        {
            "workspace_id": workspace_id,
            "semantic_model_id": semantic_model_id,
            "queries": [
                "How many orders came from the French market?",
                "the French market",
            ],
            "embedding_provider": tool.embedder,
            "top_k": 3,
        }
    ]
    assert "Semantic scope is the default analytical surface for governed business analysis." in llm.prompts[0]
    assert "- Query the governed semantic model with FROM orders_semantic." in llm.prompts[0]
    assert "Filters to apply: shopify_orders.country = 'France'" in llm.prompts[0]
    assert "shopify_orders.country ~= 'France'" in llm.prompts[0]
    assert executor.calls == [
        {
            "query": (
                "SELECT country, COUNT(*) AS order_count "
                "FROM orders_semantic "
                "WHERE country = 'France' "
                "GROUP BY country"
            ),
            "query_dialect": "postgres",
            "requested_limit": 1000,
        }
    ]
