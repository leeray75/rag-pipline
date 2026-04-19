"""Integration tests for the MCP Streamable HTTP endpoint."""

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app
from src.mcp.http_transport import mcp_starlette_app


@pytest.mark.asyncio
async def test_mcp_endpoint_route_exists():
    """POST /mcp route exists in the Starlette app."""
    # The MCP endpoint is mounted as a Starlette app
    # We verify by checking the mcp_starlette_app has the expected routes
    mcp_routes = [r for r in mcp_starlette_app.routes if hasattr(r, 'path') and 'mcp' in r.path.lower()]
    assert len(mcp_routes) > 0, "MCP routes should be registered in the Starlette app"


@pytest.mark.asyncio
async def test_health_router_route_exists():
    """Health router routes are registered."""
    health_routes = [r for r in app.routes if hasattr(r, 'path') and 'health' in r.path.lower()]
    assert len(health_routes) > 0, "Health routes should be registered in the app"
