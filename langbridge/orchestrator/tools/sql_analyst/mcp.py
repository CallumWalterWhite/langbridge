"""
Helpers for exposing the SQL analyst as an MCP server.
"""

from typing import Any, Callable, Optional

from .schemas import SQLAnalystToolInput
from .tool import SQLAnalystTool

try:  # pragma: no cover - optional dependency
    from mcp.server.fastmcp import FastMCP
except ImportError:  # pragma: no cover - optional dependency
    FastMCP = None  # type: ignore[assignment]


def _build_sql_analyst_callable(tool: SQLAnalystTool) -> Callable[..., dict[str, Any]]:
    def _callable(
        question: str,
        semantic_model_yaml: str,
        dialect: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> dict[str, Any]:
        result = tool.run_structured(
            SQLAnalystToolInput(
                question=question,
                semantic_model_yaml=semantic_model_yaml,
                dialect=dialect,
                model_name=model_name,
            )
        )
        return result.model_dump()

    return _callable


def register_sql_analyst_tool(mcp_server: Any, tool: SQLAnalystTool) -> None:
    """
    Register the SQL analyst tool on an existing MCP server instance.
    """

    sql_analyst_callable = _build_sql_analyst_callable(tool)

    if hasattr(mcp_server, "tool"):
        decorator = mcp_server.tool(name=tool.name, description=tool.description)
        decorator(sql_analyst_callable)
        return

    if hasattr(mcp_server, "add_tool"):
        mcp_server.add_tool(sql_analyst_callable, name=tool.name, description=tool.description)
        return

    raise TypeError("Unsupported MCP server implementation; expected 'tool' decorator or 'add_tool' method.")


def create_mcp_server(runnable, *, server_name: str = "sql_analyst"):
    """
    Convenience helper that spins up a FastMCP server with the SQL analyst tool
    registered. Requires the optional `mcp` dependency.
    """

    if FastMCP is None:  # pragma: no cover - optional dependency
        raise ImportError("The 'mcp' package is required to create an MCP server.")

    from .tool import create_langchain_tool

    mcp_server = FastMCP(server_name)  # type: ignore[call-arg]
    tool = create_langchain_tool(runnable)
    register_sql_analyst_tool(mcp_server, tool)
    return mcp_server


__all__ = ["register_sql_analyst_tool", "create_mcp_server"]
