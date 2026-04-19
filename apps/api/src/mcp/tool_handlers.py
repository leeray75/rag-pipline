"""MCP tool handlers — compatibility shim.

With FastMCP, tool handlers are registered directly on the server instance
via @mcp.tool() decorators in server.py. This module re-exports the mcp
instance so that any code importing from tool_handlers still works.

All tool implementations live in src/mcp/server.py.
"""

from src.mcp.server import mcp  # noqa: F401 — re-export for backwards compat

__all__ = ["mcp"]
