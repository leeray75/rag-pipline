# MCP Python SDK v1.27.0 Overview

## Quick Start

### FastMCP Framework

The Python SDK provides a high-level framework called **FastMCP** for building MCP servers with minimal boilerplate.

```python
from mcp.server import FastMCP

# Create an MCP server instance
app = FastMCP("MyServer")

# Define a tool
@app.tool()
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b

# Define a prompt
@app.prompt()
def greet(name: str) -> str:
    """Generate a greeting."""
    return f"Hello, {name}!"

# Run the server with stdio transport
if __name__ == "__main__":
    import asyncio
    asyncio.run(app.runstdio())
```

## Core Concepts

### The Three MCP Primitives

| Primitive | Control | Description | Example Use |
|-----------|---------|-------------|-------------|
| **Prompts** | User-controlled | Interactive templates invoked by user choice | Slash commands, menu options |
| **Resources** | Application-controlled | Contextual data managed by the client application | File contents, API responses |
| **Tools** | Model-controlled | Functions exposed to the LLM to take actions | API calls, data updates |

### Server Components

A FastMCP server automatically handles:

1. **Tool Discovery** - List available tools for LLM invocation
2. **Tool Execution** - Execute tools when called by the model
3. **Resource Access** - Provide access to contextual data
4. **Prompt Templates** - Define interactive prompt templates
5. **Session Management** - Handle client connections
6. **Transport** - stdio or HTTP communication

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    FastMCP Server                            │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Tools      │  │  Resources   │  │   Prompts    │      │
│  │   Handler    │  │   Handler    │  │   Handler    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│         │                 │                  │               │
│         └─────────────────┴──────────────────┘               │
│                           │                                  │
│                  ┌──────────────────┐                        │
│                  │  Session Layer   │                        │
│                  │  (Transport)     │                        │
│                  └──────────────────┘                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Client Application                        │
│  (LLM, IDE, or MCP client)                                  │
└─────────────────────────────────────────────────────────────┘
```

## Installation

### Using pip
```bash
pip install mcp
```

### Using uv
```bash
uv add mcp
```

## Transport Options

### stdio (Default for development)
```python
# Server side
asyncio.run(app.runstdio())

# Client side
from mcp import StdioClientTransport
transport = StdioClientTransport(command="python", args=["server.py"])
```

### Streamable HTTP
```python
from mcp.server import ServerSession
from fastapi import FastAPI

app = FastMCP("HTTP Server")

# Run with HTTP transport
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app.http_server(), host="0.0.0.0", port=8000)
```

## Key Features

### 1. Automatic Schema Generation
Pydantic models automatically generate JSON Schema 2020-12 compliant schemas for tool inputs and outputs.

### 2. Error Handling
Built-in error handling with `ToolError` for structured error responses.

### 3. Structured Output
Use Pydantic models for typed tool return values.

### 4. Elicitation Patterns
Support for both form mode and URL mode interactions.

### 5. Sampling
Built-in support for LLM sampling with callbacks.

### 6. Logging
Server-side logging with configurable levels.

## Common Patterns

### Tool with Error Handling
```python
@app.tool()
def process_data(data: str) -> str:
    try:
        # Process data
        return f"Processed: {data}"
    except Exception as e:
        from mcp.server import ToolError
        raise ToolError(f"Failed to process: {str(e)}")
```

### Resource with Templates
```python
@app.resource("template://file://{path}")
def read_file(path: str):
    with open(path, 'r') as f:
        return f.read()
```

### Prompt with Parameters
```python
@app.prompt()
def analyze_code(file_path: str, language: str = "python") -> str:
    """Analyze code in a file."""
    return f"Analyzing {file_path} in {language}..."
```

## Next Steps

- See [`MCP-SERVER-BUILDING.md`](MCP-SERVER-BUILDING.md) for detailed server implementation
- See [`MCP-CLIENT-IMPLEMENTATION.md`](MCP-CLIENT-IMPLEMENTATION.md) for client development
- See [`MCP-PROTOCOL-FEATURES.md`](MCP-PROTOCOL-FEATURES.md) for protocol-level details
- See [`MCP-TESTING.md`](MCP-TESTING.md) for testing strategies
