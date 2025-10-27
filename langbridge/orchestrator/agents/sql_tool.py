"""
SQL analyst tool built on top of connector abstractions.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence

from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from semantic.model import SemanticModel
from connectors.connector import (
    QueryResult,
    QueryValidationError,
    SqlConnector,
    ensure_select_statement,
)

TABLE_NAME_RE = re.compile(r"\bfrom\s+([^\s,;]+)", re.IGNORECASE)
JOIN_RE = re.compile(r"\bjoin\s+([^\s,;]+)", re.IGNORECASE)


@dataclass
class SqlGuidance:
    """
    Additional guidance for SQL generation.
    """

    goal: Optional[str] = None
    allow_tables: Optional[Sequence[str]] = None
    deny_tables: Optional[Sequence[str]] = None
    extra_instructions: Optional[str] = None
    dialect: Optional[str] = None
    max_rows: Optional[int] = 5000

#TODO: bind the semantic config to this tool
# Allows us to initalize all the tools for each purpose of the semantic model
# Question: single binding doesn't allow for cross binded queries across multiple connectors
# Maybe we need a multi-tool that can handle multiple connectors?
class SqlAnalystTool:
    """
    Helper responsible for generating, validating and executing SQL queries.
    """

    def __init__(
        self,
        *,
        connector: SqlConnector,
        semantic_model: SemanticModel,
        llm: Optional[BaseChatModel] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.connector = connector
        self.llm = llm
        self.semantic_model = semantic_model
        self.logger = logger or logging.getLogger(__name__)
        self._prompt = None
        if llm:
                semantic_yaml = self.semantic_model.yml_dump()
                self._prompt = ChatPromptTemplate.from_messages(
                    [
                        (
                            "system",
                            f"You are an expert SQL analyst. Use the following semantic model YAML to understand the database structure, relationships, metrics, and filters.\n---\n{semantic_yaml}\n---\nGenerate SQL queries that match the user's intent, using the model's relationships, metrics, and filters where appropriate. Always return a single SELECT statement unless otherwise instructed."
                        ),
                        (
                            "human",
                            "Dialect: {dialect}\nGoal: {goal}\nQuestion: {question}\nAdditional instructions: {instructions}",
                        ),
                    ]
                )
                self._chain = self._prompt | llm | StrOutputParser()
        else:
            self._chain = None

    # ------------------------------------------------------------------ #
    # SQL generation/validation
    # ------------------------------------------------------------------ #

    async def build_sql_from_nl(
        self,
        question: str,
        guidance: SqlGuidance,
    ) -> str:
        if not self._chain:
            raise RuntimeError("No LLM configured for natural language to SQL generation.")

        # The semantic YAML is now included in the system prompt, so schema_text is not needed
        instructions = guidance.extra_instructions or ""
        if guidance.allow_tables:
            instructions += f"\nUse only these tables: {', '.join(guidance.allow_tables)}."
        if guidance.deny_tables:
            instructions += f"\nDo not query these tables: {', '.join(guidance.deny_tables)}."

        sql = await self._chain.ainvoke(
            {
                "dialect": guidance.dialect or self.connector.dialect,
                "goal": guidance.goal or question,
                "question": question,
                "instructions": instructions.strip() or "Return a single SELECT statement.",
            }
        )
        return self._extract_sql(sql)

    def _extract_sql(self, raw: str) -> str:
        fenced = re.search(r"```sql\s*(.*?)```", raw, re.IGNORECASE | re.DOTALL)
        if fenced:
            return fenced.group(1).strip()
        fenced = re.search(r"```(.*?)```", raw, re.DOTALL)
        if fenced:
            return fenced.group(1).strip()
        return raw.strip()

    def validate_sql(self, sql: str, guidance: Optional[SqlGuidance] = None) -> None:
        ensure_select_statement(sql)
        tables = self._extract_tables(sql)
        if guidance:
            if guidance.allow_tables:
                disallowed = [t for t in tables if t not in set(guidance.allow_tables)]
                if disallowed:
                    raise QueryValidationError(f"Query references tables outside allow list: {', '.join(disallowed)}")
            if guidance.deny_tables:
                denied = [t for t in tables if t in set(guidance.deny_tables)]
                if denied:
                    raise QueryValidationError(f"Query references denied tables: {', '.join(denied)}")

    def _extract_tables(self, sql: str) -> List[str]:
        tables = TABLE_NAME_RE.findall(sql) + JOIN_RE.findall(sql)
        cleaned = [table.strip().strip("`\"") for table in tables]
        return [t for t in cleaned if t]

    async def run_sql(
        self,
        sql: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        guidance: Optional[SqlGuidance] = None,
    ) -> QueryResult:
        self.validate_sql(sql, guidance)
        result = await self.connector.execute(
            sql,
            params=params,
            max_rows=guidance.max_rows if guidance else 5000,
        )
        return result

    async def explain(self, sql: str) -> Dict[str, Any]:
        tables = self._extract_tables(sql)
        return {
            "sql": sql,
            "tables": tables,
            "dialect": self.connector.dialect,
        }

