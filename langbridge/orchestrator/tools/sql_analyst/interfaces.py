"""
Protocol and data model definitions for the SQL analyst tooling.
"""


from typing import Any, Optional, Protocol, Sequence

from pydantic import BaseModel, Field, field_validator


class ConnectorQueryResult(Protocol):
    """
    Runtime type returned by existing connectors.
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
    source_sql: str | None = Field(default=None, description="SQL text the connector executed.")

    @classmethod
    def from_connector(cls, result: ConnectorQueryResult) -> "QueryResult":
        return cls(
            columns=list(result.columns),
            rows=[tuple(row) for row in result.rows],
            rowcount=getattr(result, "rowcount", None),
            elapsed_ms=getattr(result, "elapsed_ms", None),
            source_sql=getattr(result, "sql", None),
        )


class SemanticModel(BaseModel):
    """
    Lightweight semantic model descriptor consumed by the SQL analyst tool.
    """

    name: str
    description: str | None = None
    connector: str | None = None
    dialect: str | None = None
    entities: dict[str, dict[str, Any]] = Field(default_factory=dict)
    joins: list[dict[str, Any]] = Field(default_factory=list)
    metrics: dict[str, dict[str, Any]] = Field(default_factory=dict)
    dimensions: dict[str, dict[str, Any]] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)

    @field_validator("entities", mode="after")
    @classmethod
    def _normalise_entity_keys(cls, value: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
        return {str(key): entity for key, entity in (value or {}).items()}
    
    
class UnifiedSemanticModel(BaseModel):
    """
    Wrapper that stitches multiple semantic models together for cross-model querying.
    """

    semantic_models: list[SemanticModel]
    version: str
    name: str | None = None
    description: Optional[str] = None
    dialect: str | None = None
    connector: str | None = None
    relationships: Optional[list[dict[str, Any]]] = None
    metrics: Optional[dict[str, dict[str, Any]]] = None
    tags: list[str] = Field(default_factory=list)


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
    semantic_search_results: dict[str, list[dict[str, Any]]] | None = Field(
        default=None,
        description="Optional pre-fetched semantic search results to assist SQL generation.",
    )


class AnalystQueryResponse(BaseModel):
    """
    Response payload emitted by the SQL analyst tool.
    """

    sql_canonical: str
    sql_executable: str
    dialect: str
    model_name: str
    result: QueryResult | None = None
    error: str | None = None
    execution_time_ms: int | None = None
