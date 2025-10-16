"""
Adapters that bridge LangChain runnables to the lightweight LLM interface used
by the SQL generator.
"""

from typing import Any

from langchain_core.messages import BaseMessage
from langchain_core.runnables import Runnable

from .generator import LLM


def _coerce_to_text(result: Any) -> str:
    """
    Convert LangChain outputs into plain text.
    """

    if isinstance(result, BaseMessage):
        return str(result.content)
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        return str(result.get("output", result))
    return str(result)


class LangChainLLMAdapter(LLM):
    """
    Thin adapter around LangChain runnables.
    """

    def __init__(self, runnable: Runnable[str, Any]):
        self._runnable = runnable

    def complete(self, prompt: str) -> str:
        result = self._runnable.invoke(prompt)
        return _coerce_to_text(result).strip()

    async def acomplete(self, prompt: str) -> str:
        result = await self._runnable.ainvoke(prompt)
        return _coerce_to_text(result).strip()


__all__ = ["LangChainLLMAdapter"]
