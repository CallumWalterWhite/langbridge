
from typing import Any

from pydantic import BaseModel, Field

class SemanticSearchResult(BaseModel):
    """Represents a single result from semantic search."""

    score: float = Field(..., description="Relevance score of the result.")
    identifier: int = Field(..., description="Unique identifier for the result.")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata associated with the result.",
    )
    
class ColumnValueSearchResult(SemanticSearchResult):
    """Represents a semantic search result specific to column values."""

    column: str = Field(..., description="Name of the column associated with the value.")
    value: str = Field(..., description="The actual value found in the column.")
    
    @classmethod
    def from_metadata(cls, metadata: dict[str, Any], score: float, identifier: int) -> "ColumnValueSearchResult":
        """Creates an instance from metadata dictionary."""
        metadata = dict(metadata or {})
        return cls(
            score=score,
            identifier=identifier,
            metadata=metadata,
            column=metadata.get("column", ""),
            value=metadata.get("value", ""),
        )
        
    def to_prompt_string(self) -> str:
        """Formats the result for inclusion in prompts."""
        return f"Column: {self.column}, Value: {self.value} (Score: {self.score:.4f})"
    
class SemanticSearchResultCollection(BaseModel):
    """Collection of semantic search results."""

    results: list[SemanticSearchResult] = Field(
        default_factory=list,
        description="List of semantic search results.",
    )
    
    def to_prompt_strings(self) -> list[str]:
        """Formats all results for inclusion in prompts."""
        return [f"ID: {res.identifier}, Score: {res.score:.4f}, Metadata: {res.metadata}" for res in self.results]
    
class ColumnValueSearchResultCollection(BaseModel):
    """Collection of column value semantic search results."""

    results: list[ColumnValueSearchResult] = Field(
        default_factory=list,
        description="List of column value search results.",
    )
    
    def to_prompt_strings(self) -> list[str]:
        """Formats all column value results for inclusion in prompts."""
        return [res.to_prompt_string() for res in self.results]
    
    @classmethod
    def from_semantic_results(
        cls, semantic_results: SemanticSearchResultCollection
    ) -> "ColumnValueSearchResultCollection":
        """Converts a collection of semantic search results to column value search results."""
        column_value_results = [
            ColumnValueSearchResult.from_metadata(
                metadata=res.metadata,
                score=res.score,
                identifier=res.identifier,
            )
            for res in semantic_results.results
        ]
        return cls(results=column_value_results)
