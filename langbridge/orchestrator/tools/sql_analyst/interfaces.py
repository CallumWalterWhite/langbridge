"""
Protocol and data model definitions for dataset-first analytical tooling.
"""


from typing import Any, List, Literal, Protocol, Sequence

from pydantic import BaseModel, Field

from semantic.model import SemanticModel


class ConnectorQueryResult(Protocol):
    """
    Generic tabular runtime result shape.
    """

    columns: Sequence[str]
    rows: Sequence[Sequence[Any]]
    elapsed_ms: int | None
    rowcount: int | None
    sql: str | None


class QueryResult(BaseModel):
    """
    Normalised query result returned by the SQL analyst tool.
    """

    columns: list[str]
    rows: list[Sequence[Any]]
    rowcount: int | None = Field(default=None)
    elapsed_ms: int | None = Field(default=None)
    source_sql: str | None = Field(default=None, description="SQL text executed by the analytical runtime.")

    @classmethod
    def from_connector(cls, result: ConnectorQueryResult) -> "QueryResult":
        return cls(
            columns=list(result.columns),
            rows=[tuple(row) for row in result.rows],
            rowcount=getattr(result, "rowcount", None),
            elapsed_ms=getattr(result, "elapsed_ms", None),
            source_sql=getattr(result, "sql", None),
        )


class AnalystQueryRequest(BaseModel):
    """
    Request payload for the SQL analyst tool.
    """

    question: str = Field(..., min_length=1)
    conversation_context: str | None = Field(
        default=None,
        description="Optional conversation history to help interpret follow-up questions.",
    )
    filters: dict[str, Any] | None = None
    limit: int | None = Field(default=1000, ge=1)
    semantic_search_result_prompts: List[str] | None = Field(
        default=None,
        description="Optional list of formatted semantic search results to include in the prompt.",
    )


class AnalyticalColumn(BaseModel):
    name: str
    data_type: str | None = None
    description: str | None = None


class AnalyticalField(BaseModel):
    name: str
    synonyms: list[str] = Field(default_factory=list)


class AnalyticalMetric(BaseModel):
    name: str
    expression: str | None = None
    description: str | None = None


class AnalyticalDatasetBinding(BaseModel):
    dataset_id: str
    dataset_name: str
    sql_alias: str
    description: str | None = None
    source_kind: str | None = None
    storage_kind: str | None = None
    columns: list[AnalyticalColumn] = Field(default_factory=list)


class AnalyticalContext(BaseModel):
    asset_type: Literal["dataset", "semantic_model"]
    asset_id: str
    asset_name: str
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    execution_mode: Literal["federated"] = "federated"
    dialect: str = "postgres"
    datasets: list[AnalyticalDatasetBinding] = Field(default_factory=list)
    tables: list[str] = Field(default_factory=list)
    dimensions: list[AnalyticalField] = Field(default_factory=list)
    measures: list[AnalyticalField] = Field(default_factory=list)
    metrics: list[AnalyticalMetric] = Field(default_factory=list)
    relationships: list[str] = Field(default_factory=list)


class AnalystQueryResponse(BaseModel):
    """
    Response payload emitted by the SQL analyst tool.
    """

    analysis_path: Literal["dataset", "semantic_model"]
    execution_mode: Literal["federated"]
    asset_type: Literal["dataset", "semantic_model"]
    asset_id: str
    asset_name: str
    sql_canonical: str
    sql_executable: str
    dialect: str
    selected_datasets: list[AnalyticalDatasetBinding] = Field(default_factory=list)
    result: QueryResult | None = None
    error: str | None = None
    execution_time_ms: int | None = None


class FederatedSqlExecutor(Protocol):
    async def execute_sql(
        self,
        *,
        sql: str,
        dialect: str,
        max_rows: int | None = None,
    ) -> QueryResult:
        ...
