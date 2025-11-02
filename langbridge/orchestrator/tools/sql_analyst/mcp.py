"""
Helpers for exposing the SQL analyst as an MCP server.

The MCP surface is considered legacy and remains synchronous for backwards compatibility.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from .interfaces import AnalystQueryRequest
from .tool import SqlAnalystTool

try:  # pragma: no cover - optional dependency
    from mcp.server.fastmcp import FastMCP
except ImportError:  # pragma: no cover - optional dependency
    FastMCP = None  # type: ignore[assignment]


def _build_sql_analyst_callable(tool: SqlAnalystTool) -> Callable[..., dict[str, Any]]:
    def _callable(
        question: str,
        *,
        limit: Optional[int] = None,
        filters: Optional[dict[str, Any]] = None,
        **_: Any,
    ) -> dict[str, Any]:
        """
        Synchronous bridge that invokes the refactored SqlAnalystTool.
        """

        request = AnalystQueryRequest(question=question, limit=limit, filters=filters)
        response = tool.run(request)
        return response.model_dump()

    return _callable


def register_sql_analyst_tool(mcp_server: Any, tool: SqlAnalystTool) -> None:
    """
    Register the SQL analyst tool on an existing MCP server instance.
    """

    sql_analyst_callable = _build_sql_analyst_callable(tool)

    if hasattr(mcp_server, "tool"):
        decorator = mcp_server.tool(name=tool.name, description=f"SQL analyst for {tool.name}")
        decorator(sql_analyst_callable)
        return

    if hasattr(mcp_server, "add_tool"):
        mcp_server.add_tool(sql_analyst_callable, name=tool.name, description=f"SQL analyst for {tool.name}")
        return

    raise TypeError("Unsupported MCP server implementation; expected 'tool' decorator or 'add_tool' method.")


def create_mcp_server(tool: SqlAnalystTool, *, server_name: str = "sql_analyst"):
    """
    Convenience helper that spins up a FastMCP server with the SQL analyst tool
    registered. Requires the optional `mcp` dependency.
    """

    if FastMCP is None:  # pragma: no cover - optional dependency
        raise ImportError("The 'mcp' package is required to create an MCP server.")

    mcp_server = FastMCP(server_name)  # type: ignore[call-arg]
    register_sql_analyst_tool(mcp_server, tool)
    return mcp_server


__all__ = ["register_sql_analyst_tool", "create_mcp_server"]
