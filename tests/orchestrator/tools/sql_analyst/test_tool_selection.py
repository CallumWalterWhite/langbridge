import pathlib
import sys
import uuid

sys.path.append(str(pathlib.Path(__file__).resolve().parents[5] / "langbridge" / "langbridge"))

from langbridge.orchestrator.agents.analyst.selector import AnalyticalContextSelector
from langbridge.orchestrator.definitions import AnalystQueryScopePolicy
from langbridge.orchestrator.tools.sql_analyst.interfaces import (
    AnalyticalColumn,
    AnalyticalContext,
    AnalyticalDatasetBinding,
    AnalyticalMetric,
    AnalystQueryRequest,
)
from langbridge.runtime.models import SqlQueryScope


class StaticLLM:
    def __init__(self, payload: str = "{}") -> None:
        self._payload = payload

    def complete(self, prompt: str, *, temperature: float = 0.0, max_tokens: int | None = None) -> str:
        _ = (prompt, temperature, max_tokens)
        return self._payload


class _FakeTool:
    def __init__(
        self,
        *,
        binding_name: str,
        asset_name: str,
        asset_type: str,
        query_scope: SqlQueryScope,
        query_scope_policy: AnalystQueryScopePolicy,
        keywords: set[str],
        priority: int = 0,
        metric_name: str | None = None,
        tags: list[str] | None = None,
    ) -> None:
        self.binding_name = binding_name
        self.binding_description = f"{binding_name} binding"
        self.query_scope_policy = query_scope_policy
        self.priority = priority
        self._keywords = set(keywords)
        self.context = AnalyticalContext(
            query_scope=query_scope,
            asset_type=asset_type,
            asset_id=str(uuid.uuid4()),
            asset_name=asset_name,
            description=f"{asset_name} asset",
            tags=tags or [],
            datasets=[
                AnalyticalDatasetBinding(
                    dataset_id=str(uuid.uuid4()),
                    dataset_name=f"{asset_name}_dataset",
                    sql_alias=asset_name.replace("_model", "").replace("_dataset", ""),
                    source_kind="connector",
                    storage_kind="table",
                    columns=[AnalyticalColumn(name="id", data_type="integer")],
                )
            ],
            tables=[asset_name.replace("_model", "").replace("_dataset", "")],
            metrics=[AnalyticalMetric(name=metric_name, expression="COUNT(*)")] if metric_name else [],
        )

    @property
    def name(self) -> str:
        return self.context.asset_name

    @property
    def query_scope(self) -> SqlQueryScope:
        return self.context.query_scope

    def selection_keywords(self) -> set[str]:
        return set(self._keywords)

    def describe_for_selection(self, *, tool_id: str) -> dict[str, object]:
        return {
            "id": tool_id,
            "binding_name": self.binding_name,
            "query_scope_policy": self.query_scope_policy.value,
            "query_scope": self.query_scope.value,
            "asset_name": self.context.asset_name,
            "asset_type": self.context.asset_type,
            "metrics": [metric.name for metric in self.context.metrics],
            "datasets": [dataset.dataset_name for dataset in self.context.datasets],
            "tags": list(self.context.tags),
        }


def test_selector_chooses_matching_binding_before_asset_selection() -> None:
    selector = AnalyticalContextSelector(
        StaticLLM(),
        [
            _FakeTool(
                binding_name="customers",
                asset_name="customers_dataset",
                asset_type="dataset",
                query_scope=SqlQueryScope.dataset,
                query_scope_policy=AnalystQueryScopePolicy.dataset_only,
                keywords={"customers", "segment"},
            ),
            _FakeTool(
                binding_name="orders",
                asset_name="orders_dataset",
                asset_type="dataset",
                query_scope=SqlQueryScope.dataset,
                query_scope_policy=AnalystQueryScopePolicy.dataset_only,
                keywords={"orders", "revenue"},
                tags=["revenue"],
            ),
        ],
    )

    selection = selector.select_binding(AnalystQueryRequest(question="Show revenue by orders"))

    assert selection.binding_name == "orders"
    assert selection.initial_scope == SqlQueryScope.dataset


def test_selector_selects_asset_within_scope_after_binding_choice() -> None:
    selector = AnalyticalContextSelector(
        StaticLLM(),
        [
            _FakeTool(
                binding_name="governed",
                asset_name="retention_model",
                asset_type="semantic_model",
                query_scope=SqlQueryScope.semantic,
                query_scope_policy=AnalystQueryScopePolicy.semantic_only,
                keywords={"retention", "churn"},
                metric_name="retention",
            ),
            _FakeTool(
                binding_name="governed",
                asset_name="revenue_model",
                asset_type="semantic_model",
                query_scope=SqlQueryScope.semantic,
                query_scope_policy=AnalystQueryScopePolicy.semantic_only,
                keywords={"revenue", "sales"},
                metric_name="revenue",
            ),
        ],
    )

    request = AnalystQueryRequest(question="Give me retention KPI results")
    selection = selector.select_binding(request)
    tool = selector.select_tool(
        request,
        binding_name=selection.binding_name,
        query_scope=selection.initial_scope,
    )

    assert selection.binding_name == "governed"
    assert selection.initial_scope == SqlQueryScope.semantic
    assert tool.name == "retention_model"


def test_selector_prefers_semantic_scope_for_semantic_preferred_binding() -> None:
    selector = AnalyticalContextSelector(
        StaticLLM(),
        [
            _FakeTool(
                binding_name="sales",
                asset_name="sales_model",
                asset_type="semantic_model",
                query_scope=SqlQueryScope.semantic,
                query_scope_policy=AnalystQueryScopePolicy.semantic_preferred,
                keywords={"sales", "revenue"},
                metric_name="revenue",
            ),
            _FakeTool(
                binding_name="sales",
                asset_name="sales_dataset",
                asset_type="dataset",
                query_scope=SqlQueryScope.dataset,
                query_scope_policy=AnalystQueryScopePolicy.semantic_preferred,
                keywords={"sales", "revenue"},
            ),
        ],
    )

    selection = selector.select_binding(AnalystQueryRequest(question="Revenue by region"))

    assert selection.binding_name == "sales"
    assert selection.initial_scope == SqlQueryScope.semantic
    assert set(selection.available_scopes) == {SqlQueryScope.semantic, SqlQueryScope.dataset}
    assert selector.fallback_scope(selection, current_scope=SqlQueryScope.semantic) == SqlQueryScope.dataset


def test_selector_uses_dataset_scope_for_dataset_only_policy() -> None:
    selector = AnalyticalContextSelector(
        StaticLLM(),
        [
            _FakeTool(
                binding_name="sales",
                asset_name="sales_model",
                asset_type="semantic_model",
                query_scope=SqlQueryScope.semantic,
                query_scope_policy=AnalystQueryScopePolicy.dataset_only,
                keywords={"sales", "revenue"},
                metric_name="revenue",
            ),
            _FakeTool(
                binding_name="sales",
                asset_name="sales_dataset",
                asset_type="dataset",
                query_scope=SqlQueryScope.dataset,
                query_scope_policy=AnalystQueryScopePolicy.dataset_only,
                keywords={"sales", "revenue"},
            ),
        ],
    )

    selection = selector.select_binding(AnalystQueryRequest(question="Revenue by region"))

    assert selection.initial_scope == SqlQueryScope.dataset
    assert selector.fallback_scope(selection, current_scope=SqlQueryScope.dataset) is None
