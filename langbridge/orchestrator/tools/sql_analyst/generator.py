"""
Core SQL generation pipeline for the SQL analyst tool.
"""


#TODO: remove
import re
from typing import Optional

from .loader import load_semantic_model_yaml
from .prompt_builder import build_prompt
from .resolver import ResolvedModel, build_resolved_model
from semantic import SemanticModel

SQL_FENCE_RE = re.compile(r"```sql\s*(.*?)\s*```", re.IGNORECASE | re.DOTALL)


def extract_sql_from_text(text: str) -> str:
    """
    Extract SQL text from the LLM response.
    """

    match = SQL_FENCE_RE.search(text)
    if match:
        return match.group(1).strip()
    return text.strip()


class SQLGenerator:
    """
    Encapsulates the semantic-model to SQL generation pipeline.
    """

    def __init__(self, llm: "LLM"):
        self._llm = llm

    def generate(
        self,
        semantic_model_yaml: str,
        user_request: str,
        dialect: Optional[str] = None,
    ) -> str:
        model = load_semantic_model_yaml(semantic_model_yaml)
        _resolved: ResolvedModel = build_resolved_model(model)
        prompt = build_prompt(model, user_request, dialect)
        raw = self._llm.complete(prompt)
        return extract_sql_from_text(raw)

    async def agenerate(
        self,
        semantic_model_yaml: str,
        user_request: str,
        dialect: Optional[str] = None,
    ) -> str:
        model = load_semantic_model_yaml(semantic_model_yaml)
        _resolved: ResolvedModel = build_resolved_model(model)
        prompt = build_prompt(model, user_request, dialect)
        raw = await self._llm.acomplete(prompt)
        return extract_sql_from_text(raw)


class LLM:
    """
    Interface protocol implemented by LLM adapters.
    """

    def complete(self, prompt: str) -> str:  # pragma: no cover - protocol type
        raise NotImplementedError

    async def acomplete(self, prompt: str) -> str:  # pragma: no cover - protocol type
        raise NotImplementedError


__all__ = ["SQLGenerator", "LLM", "extract_sql_from_text"]
