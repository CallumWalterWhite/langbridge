"""
High-level orchestration logic for the SQL analyst tool.
"""

from typing import Optional

from .generator import SQLGenerator
from .schemas import SQLAnalystToolInput, SQLAnalystToolResult


class SQLAnalystError(RuntimeError):
    """Base error type for SQL analyst failures."""


class SQLAnalystService:
    """
    Service that turns natural language questions into SQL queries.
    """

    def __init__(self, generator: SQLGenerator, default_dialect: str = "ansi"):
        self._generator = generator
        self._default_dialect = default_dialect

    def generate_sql(
        self,
        question: str,
        semantic_model_yaml: str,
        *,
        dialect: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> SQLAnalystToolResult:
        dialect_to_use = dialect or self._default_dialect
        sql = self._generator.generate(semantic_model_yaml, question, dialect_to_use)
        if not sql:
            raise SQLAnalystError("The language model returned an empty SQL query.")

        return SQLAnalystToolResult(
            sql=sql,
            dialect=dialect_to_use,
            model_name=model_name,
        )

    async def agenerate_sql(
        self,
        question: str,
        semantic_model_yaml: str,
        *,
        dialect: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> SQLAnalystToolResult:
        dialect_to_use = dialect or self._default_dialect
        sql = await self._generator.agenerate(semantic_model_yaml, question, dialect_to_use)
        if not sql:
            raise SQLAnalystError("The language model returned an empty SQL query.")

        return SQLAnalystToolResult(
            sql=sql,
            dialect=dialect_to_use,
            model_name=model_name,
        )


def create_service(llm_adapter) -> SQLAnalystService:
    """
    Convenience factory to build a service from an LLM adapter.
    """

    return SQLAnalystService(SQLGenerator(llm_adapter))


__all__ = ["SQLAnalystService", "SQLAnalystError", "create_service"]
