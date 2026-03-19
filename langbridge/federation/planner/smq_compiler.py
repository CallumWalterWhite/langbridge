from __future__ import annotations

from federation.models.smq import SMQQuery
from semantic.model import SemanticModel
from semantic.query import SemanticQuery, SemanticQueryEngine


class SMQCompiler:
    def __init__(self) -> None:
        self._engine = SemanticQueryEngine()

    def compile_to_sql(
        self,
        *,
        query: SMQQuery,
        semantic_model: SemanticModel,
        dialect: str = "tsql",
    ) -> str:
        semantic_query = SemanticQuery.model_validate(
            query.model_dump(by_alias=True, exclude_none=True)
        )
        return self._engine.compile(
            semantic_query,
            semantic_model,
            dialect=dialect,
        ).sql
