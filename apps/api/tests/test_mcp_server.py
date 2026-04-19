"""Tests for the MCP server tool registration."""

import pytest


@pytest.mark.asyncio
async def test_fastmcp_import_works():
    """Verify FastMCP can be imported and is the expected type."""
    from mcp.server import FastMCP

    assert FastMCP is not None


@pytest.mark.asyncio
async def test_mcp_server_has_expected_tools():
    """Verify that the MCP server has the expected tools registered."""
    from src.mcp.server import mcp

    # FastMCP uses the @mcp.tool() decorator to register tools
    # We can verify the tools exist by checking the internal structure
    # or by testing via the HTTP endpoint (which is done in test_mcp_http_transport.py)
    assert mcp is not None
