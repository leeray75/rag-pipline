"""Streamable HTTP transport — mounts the MCP server into the FastAPI app.

The Streamable HTTP transport exposes a single endpoint:
    POST /mcp

This replaces the legacy two-endpoint SSE pattern (GET /mcp/sse + POST /mcp/messages/).
Streaming clients send Accept: text/event-stream and receive an SSE response
from within the same POST handler. Non-streaming clients receive plain JSON.

Integration pattern:
    FastMCP.streamable_http_app() returns a Starlette ASGI app.
    We mount it into FastAPI with app.mount("/mcp", mcp_starlette_app).
    The session manager lifecycle is managed in the FastAPI lifespan.

MCP spec reference:
    https://modelcontextprotocol.io/specification/2025-03-26/basic/transports
"""

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from starlette.applications import Starlette

from src.mcp.server import mcp

logger = logging.getLogger(__name__)

# Build the Starlette ASGI app from FastMCP.
# FastMCP.streamable_http_app() creates a StreamableHTTPSessionManager
# and wraps it in a Starlette app with the correct route at "/mcp".
# We mount this at "/" so that FastAPI's app.mount("/mcp", ...) maps
# incoming /mcp requests to the Starlette app's internal "/mcp" route.
mcp_starlette_app: Starlette = mcp.streamable_http_app()


@asynccontextmanager
async def mcp_lifespan() -> AsyncGenerator[None, None]:
    """Async context manager that runs the MCP session manager lifecycle.

    Must be called from within the FastAPI application lifespan so that
    the StreamableHTTPSessionManager task group is active for the full
    duration of the server process.
    """
    async with mcp.session_manager.run():
        logger.info("MCP Streamable HTTP session manager started at POST /mcp")
        yield
        logger.info("MCP Streamable HTTP session manager stopped")
