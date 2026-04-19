# MCP Testing Guide

## Testing Overview

The Python SDK provides `create_connected_server_and_client_session` function to create a session using an in-memory transport for testing purposes.

## Dependencies

### Required Testing Libraries

```bash
# Using pip
pip install inline-snapshot pytest

# Using uv
uv add inline-snapshot pytest
```

### Library Descriptions

| Library | Purpose |
|---------|---------|
| **pytest** | Standard Python testing framework |
| **inline-snapshot** | Snapshot testing for cleaner test assertions |

## Basic Test Setup

### Server Code (server.py)
```python
from mcp.server import FastMCP

app = FastMCP("Calculator")

@app.tool()
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b

@app.tool()
def multiply(a: int, b: int) -> int:
    """Multiply two numbers."""
    return a * b
```

### Test File (test_server.py)
```python
from collections.abc import AsyncGenerator

import pytest
from inline_snapshot import snapshot
from mcp.client.session import ClientSession
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import CallToolResult, TextContent

from server import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client_session() -> AsyncGenerator[ClientSession]:
    async with create_connected_server_and_client_session(app, raise_exceptions=True) as _session:
        yield _session


@pytest.mark.anyio
async def test_call_add_tool(client_session: ClientSession):
    result = await client_session.call_tool("add", {"a": 1, "b": 2})
    assert result == snapshot(
        CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text="3"
                )
            ],
            structuredContent={"result": 3},
        )
    )
```

## Test Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Test File                                 │
├─────────────────────────────────────────────────────────────┤
│  ┌────────────────┐  ┌──────────────────┐                  │
│  │   Server Fix   │  │  Client Session  │                  │
│  │  (app.py)      │  │   (test)         │                  │
│  └────────┬───────┘  └─────────┬─────────┘                  │
│           │                     │                            │
│           └──────────┬──────────┘                            │
│                      │                                       │
│         ┌──────────────────────┐                             │
│         │  in-memory transport │                             │
│         └──────────────────────┘                             │
└─────────────────────────────────────────────────────────────┘
```

## Testing Patterns

### 1. Testing Tool Execution
```python
@pytest.mark.anyio
async def test_tool_with_multiple_args(client_session: ClientSession):
    result = await client_session.call_tool(
        "multiply",
        {"a": 3, "b": 4}
    )
    assert result.structuredContent == {"result": 12}
```

### 2. Testing Error Handling
```python
from mcp.server import ToolError

@pytest.mark.anyio
async def test_tool_error(client_session: ClientSession):
    with pytest.raises(Exception):
        result = await client_session.call_tool(
            "divide",
            {"a": 10, "b": 0}
        )
```

### 3. Testing Resource Access
```python
@pytest.mark.anyio
async def test_read_resource(client_session: ClientSession):
    result = await client_session.read_resource("file:///path/to/file.txt")
    assert len(result.contents) > 0
```

### 4. Testing Prompt Templates
```python
@pytest.mark.anyio
async def test_list_prompts(client_session: ClientSession):
    prompts = await client_session.list_prompts()
    assert len(prompts.prompts) > 0
    
@pytest.mark.anyio
async def test_call_prompt(client_session: ClientSession):
    result = await client_session.call_prompt(
        "greeting",
        {"name": "Alice"}
    )
    assert "Hello" in result.content
```

### 5. Testing Tool List
```python
@pytest.mark.anyio
async def test_list_tools(client_session: ClientSession):
    tools = await client_session.list_tools()
    tool_names = [tool.name for tool in tools.tools]
    assert "add" in tool_names
    assert "multiply" in tool_names
```

## Snapshot Testing

### Using inline-snapshot
```python
from inline_snapshot import snapshot

# Capture the exact output for later comparison
result = await client_session.call_tool("add", {"a": 1, "b": 2})
assert result == snapshot(
    CallToolResult(
        content=[TextContent(type="text", text="3")],
        structuredContent={"result": 3},
    )
)
```

## Running Tests

### Basic Test Execution
```bash
# Run all tests
pytest

# Run specific test file
pytest test_server.py

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=server --cov-report=html
```

### Interactive Test Development
```bash
# Stop after first failure
pytest -x

# Show local variables in tracebacks
pytest -l

# Run tests that match a pattern
pytest -k "tool"
```

## Best Practices

### 1. Use Fixtures for Reusable Setup
```python
@pytest.fixture
async def client_session():
    async with create_connected_server_and_client_session(
        app, 
        raise_exceptions=True
    ) as session:
        yield session
```

### 2. Test All Tool Parameters
```python
@pytest.mark.parametrize("a,b,expected", [
    (1, 2, 3),
    (0, 0, 0),
    (-1, 1, 0),
    (100, 200, 300),
])
@pytest.mark.anyio
async def test_add_parametrized(client_session, a, b, expected):
    result = await client_session.call_tool("add", {"a": a, "b": b})
    assert result.structuredContent["result"] == expected
```

### 3. Test Resource Types
```python
@pytest.mark.anyio
async def test_binary_resource(client_session):
    result = await client_session.read_resource("image://file.png")
    # Check for blob content type
    assert any(c.type == "blob" for c in result.contents)
```

### 4. Test Empty Results
```python
@pytest.mark.anyio
async def test_empty_tool_result(client_session):
    result = await client_session.call_tool("no_op")
    assert result.content == []
    assert result.structuredContent is None
```

## Common Test Scenarios

### Testing Server Initialization
```python
@pytest.mark.anyio
async def test_server_initialization(client_session):
    # Initialize session
    await client_session.initialize()
    
    # Verify server is ready
    assert client_session.can_send()
```

### Testing Tool Metadata
```python
@pytest.mark.anyio
async def test_tool_metadata(client_session):
    tools = await client_session.list_tools()
    add_tool = next(t for t in tools.tools if t.name == "add")
    assert add_tool.description is not None
    assert add_tool.inputSchema is not None
```

### Testing Pagination
```python
@pytest.mark.anyio
async def test_pagination(client_session):
    resources = await client_session.list_resources()
    # Verify pagination fields
    assert hasattr(resources, 'resources')
    assert hasattr(resources, 'next_cursor')
```
