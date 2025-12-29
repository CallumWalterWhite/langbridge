"""
Public API for the refactored SQL analyst tool package.

Legacy exports from the previous LangChain-oriented implementation remain available
for backwards compatibility but are not part of the new orchestrator pathway.
"""

from .interfaces import (
    AnalystQueryRequest,
    AnalystQueryResponse,
    QueryResult,
    SemanticModel,
    UnifiedSemanticModel,
)
from .semantic_loader import SemanticModelError, load_semantic_model
from .tool import SqlAnalystTool

# Legacy interfaces (retain for compatibility with existing integrations)
from .llm_adapter import LangChainLLMAdapter  # noqa: E402
from .mcp import create_mcp_server, register_sql_analyst_tool  # noqa: E402
from .service import SQLAnalystError, SQLAnalystService, create_service  # noqa: E402

__all__ = [
    "AnalystQueryRequest",
    "AnalystQueryResponse",
    "QueryResult",
    "SemanticModel",
    "SqlAnalystTool",
    "SemanticModelError",
    "load_semantic_model",
    "UnifiedSemanticModel",
    # Legacy exports
    "LangChainLLMAdapter",
    "SQLAnalystService",
    "SQLAnalystError",
    "create_service",
    "register_sql_analyst_tool",
    "create_mcp_server",
]
