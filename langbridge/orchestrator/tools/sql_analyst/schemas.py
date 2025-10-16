"""
Data schemas for the SQL analyst tool.

These Pydantic models cover both the semantic model definition that the
tool consumes and the structured inputs/outputs exposed to LangChain/MCP
integrations.
"""
from typing import List, Optional

from pydantic import BaseModel, Field


class SQLAnalystToolInput(BaseModel):
    """
    Structured input schema expected by the SQL analyst tool.

    Attributes
    ----------
    question:
        Natural language question the user wants to answer.
    semantic_model_yaml:
        YAML string describing the semantic model relevant for this request.
    model_name:
        Optional identifier for the semantic model. Useful when callers keep
        a catalogue of models and want the response to indicate which one was
        used.
    dialect:
        Optional SQL dialect hint (e.g. "postgres", "snowflake"). Defaults to
        ANSI when omitted.
    """

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
    """
    Standardised output produced by the SQL analyst tool.
    """

    sql: str = Field(..., description="Generated SQL query text.")
    dialect: str = Field(..., description="Dialect that the SQL was generated for.")
    model_name: Optional[str] = Field(
        default=None,
        description="Identifier of the semantic model that backed this response.",
    )
    warnings: List[str] = Field(default_factory=list, description="Non-fatal warnings emitted during generation.")


__all__ = [
    "SQLAnalystToolInput",
    "SQLAnalystToolResult"
]
