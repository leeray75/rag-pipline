# Building MCP Servers with FastMCP

## Server Basics

### Creating a Server Instance

```python
from mcp.server import FastMCP

# Create server with a name
app = FastMCP("MyServer")

# Register a tool
@app.tool(
    name="calculate",
    description="Calculate mathematical expressions",
)
def calculate(expression: str) -> float:
    """Evaluate a mathematical expression."""
    return eval(expression)  # Note: In production, use a safer parser
```

### Running the Server

```python
import asyncio

# Run with stdio transport (default for development)
if __name__ == "__main__":
    asyncio.run(app.runstdio())

# Run with HTTP transport
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app.http_server(), host="0.0.0.0", port=8000)
```

## Tool Definitions

### Basic Tool
```python
@app.tool()
def simple_tool(input: str) -> str:
    """A simple tool with string input/output."""
    return f"Processed: {input}"
```

### Tool with Multiple Parameters
```python
@app.tool()
def search(
    query: str,
    max_results: int = 10,
    include_duplicates: bool = False
) -> list[str]:
    """Search for items matching the query."""
    # Implementation here
    pass
```

### Tool with Pydantic Model Input
```python
from pydantic import BaseModel, Field

class SearchParams(BaseModel):
    query: str = Field(description="Search query string")
    max_results: int = Field(default=10, description="Maximum results to return")
    category: str | None = Field(default=None, description="Optional category filter")

@app.tool()
def search(params: SearchParams) -> list[str]:
    """Search with structured parameters."""
    # Access params.query, params.max_results, etc.
    pass
```

### Tool with Structured Output (Pydantic)
```python
from pydantic import BaseModel

class SearchResult(BaseModel):
    title: str
    description: str
    relevance_score: float

@app.tool()
def search_detailed(query: str) -> list[SearchResult]:
    """Search returning structured results."""
    # Return list of SearchResult objects
    pass
```

## Resource Definitions

### Simple Resource
```python
@app.resource("file:///{path}")
def read_file(path: str) -> str:
    """Read a text file."""
    with open(path, 'r') as f:
        return f.read()
```

### Resource with Template Parameters
```python
# Pattern: template://protocol://host/{param1}/{param2}
@app.resource("api://{host}/{endpoint}")
def api_resource(host: str, endpoint: str) -> str:
    """Fetch data from an API."""
    import requests
    url = f"https://{host}/{endpoint}"
    return requests.get(url).text
```

### Binary Resources
```python
@app.resource("image:///{path}")
def read_image(path: str) -> bytes:
    """Read an image file as binary data."""
    with open(path, 'rb') as f:
        return f.read()
```

### Resource Subscriptions
```python
@app.resource("watch:///{path}")
def watch_file(path: str):
    """Watch a file for changes and notify client."""
    import time
    import os
    
    # Initial content
    with open(path, 'r') as f:
        content = f.read()
    
    # Watch for changes (in production, use inotify or similar)
    mtime = os.path.getmtime(path)
    while True:
        time.sleep(1)
        new_mtime = os.path.getmtime(path)
        if new_mtime != mtime:
            with open(path, 'r') as f:
                content = f.read()
            # Notify client of change
            yield content
            mtime = new_mtime
```

## Prompt Definitions

### Basic Prompt
```python
@app.prompt()
def basic_prompt(name: str) -> str:
    """Simple prompt with one parameter."""
    return f"Hello, {name}! How can I help you today?"
```

### Prompt with Multiple Parameters
```python
@app.prompt()
def code_review_prompt(
    code: str,
    language: str,
    focus_areas: list[str] | None = None
) -> str:
    """Generate a code review prompt."""
    areas = ", ".join(focus_areas) if focus_areas else "general"
    return f"""
Review the following {language} code for {areas} issues:

```{language}
{code}
```
"""
```

## Error Handling

### ToolError for Tool Failures
```python
from mcp.server import ToolError

@app.tool()
def dangerous_operation(value: str) -> str:
    if not value:
        raise ToolError("Value cannot be empty")
    try:
        return int(value) * 2
    except ValueError:
        raise ToolError("Value must be a number")
```

### Error Response Pattern
```python
@app.tool()
def api_call(endpoint: str) -> str:
    try:
        import requests
        response = requests.get(f"https://api.example.com/{endpoint}")
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        raise ToolError(f"API request failed: {str(e)}")
```

## Server Capabilities

### Automatic Capability Declaration

FastMCP automatically declares capabilities based on registered handlers:

| Capability | Flag | Declared When |
|------------|------|---------------|
| prompts | listChanged | `@app.prompt()` handler registered |
| resources | subscribe, listChanged | `@app.resource()` handler registered |
| tools | listChanged | `@app.tool()` handler registered |
| logging | - | `set_logging_level` handler registered |
| completions | - | `completion` handler registered |

### Inspecting Server Capabilities
```python
# On the client side
capabilities = session.get_server_capabilities()
if capabilities and capabilities.tools:
    tools = await session.list_tools()
```

## Logging and Notifications

### Server-Side Logging
```python
import logging

@app.tool()
def operation() -> str:
    logging.info("Starting operation")
    try:
        # Do work
        logging.info("Operation completed successfully")
        return "Success"
    except Exception as e:
        logging.error(f"Operation failed: {e}")
        raise
```

### Sending Notifications
```python
from mcp.types import Notification

@app.tool()
def long_operation() -> str:
    # Send progress notification
    session.send_notification(Notification(
        method="notifications/progress",
        params={"message": "Processing...", "progress": 50}
    ))
    return "Done"
```

## Next Steps

- See [`MCP-PROTOCOL-FEATURES.md`](MCP-PROTOCOL-FEATURES.md) for protocol-level features
- See [`MCP-CLIENT-IMPLEMENTATION.md`](MCP-CLIENT-IMPLEMENTATION.md) for client development
- See [`MCP-TESTING.md`](MCP-TESTING.md) for testing strategies
