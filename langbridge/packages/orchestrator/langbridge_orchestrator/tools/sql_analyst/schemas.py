"""
Legacy data schemas retained for backwards compatibility with existing tooling.
"""
from typing import List, Optional

from pydantic import BaseModel, Field


class SQLAnalystToolInput(BaseModel):
    question: str = Field(..., min_length=1, description="Natural language request to translate to SQL.")
    semantic_model_yaml: str = Field(
        ...,
        min_length=1,
        description="YAML representation of the semantic model selected for this request.",
    )
    model_name: Optional[str] = Field(
        default=None,
        description="Optional identifier for the semantic model used for provenance tracking.",
    )
    dialect: Optional[str] = Field(
        default=None,
        description="Optional SQL dialect hint to steer SQL synthesis.",
    )


class SQLAnalystToolResult(BaseModel):
    sql: str = Field(..., description="Generated SQL query text.")
    dialect: str = Field(..., description="Dialect that the SQL was generated for.")
    model_name: Optional[str] = Field(
        default=None,
        description="Identifier of the semantic model that backed this response.",
    )
    warnings: List[str] = Field(default_factory=list, description="Non-fatal warnings emitted during generation.")


__all__ = ["SQLAnalystToolInput", "SQLAnalystToolResult"]

