# Writing MCP Clients with Python SDK

## Client Basics

### Creating a Client Session

```python
from mcp import ClientSession
from mcp.client.session import create_connected_server_and_client_session
from mcp.types import CallToolResult, TextContent

# Method 1: Using in-memory transport (for testing)
async with create_connected_server_and_client_session(server_app) as session:
    # Use session
    pass

# Method 2: Using stdio transport
from mcp.client.stdio import StdioClientTransport
transport = StdioClientTransport(command="python", args=["server.py"])
async with ClientSession(transport) as session:
    # Initialize session
    await session.initialize()
    # Use session
    pass
```

### Session Initialization

```python
async with ClientSession(transport) as session:
    # Initialize with optional capabilities
    result = await session.initialize(
        protocol_version="2024-11-05",
        capabilities={},
        client_info={
            "name": "my-client",
            "version": "1.0.0"
        }
    )
    
    # Check server info
    server_info = result.server_info
    capabilities = result.capabilities
```

## Tool Invocation

### Calling a Tool
```python
# Basic tool call
result = await session.call_tool(
    tool_name="add",
    arguments={"a": 1, "b": 2}
)

# Process tool result
for content in result.content:
    if content.type == "text":
        print(content.text)
    elif content.type == "image":
        print(f"Image: {content.data}")
```

### Handling Tool Results
```python
class ToolResult:
    content: list[Content]  # Text, Image, Embedding, etc.
    structured_content: dict | list | None  # JSON-serializable structured data
    error: str | None  # Error message if tool failed
    logs: list[str]  # Tool execution logs
```

## Resource Access

### Listing Resources
```python
# List all available resources
resources = await session.list_resources()

# Read a resource
resource_uri = "file:///path/to/file.txt"
result = await session.read_resource(uri=resource_uri)

# Process resource content
for content in result.contents:
    if content.type == "text":
        print(content.text)
    elif content.type == "blob":
        import base64
        data = base64.b64decode(content.blob)
```

### Resource Subscriptions
```python
# Subscribe to resource changes
async with session.subscribe_resources(["file:///path/to/file.txt"]) as changes:
    async for change in changes:
        print(f"Resource changed: {change.uri}")
        # Read updated resource
        result = await session.read_resource(change.uri)
```

## Prompt Templates

### Listing Prompts
```python
# Get available prompts
prompts = await session.list_prompts()

# Get prompt details
for prompt in prompts:
    print(f"Prompt: {prompt.name}")
    print(f"Description: {prompt.description}")
    print(f"Arguments: {prompt.arguments}")
```

### Invoking a Prompt
```python
# Get a specific prompt
prompt = await session.get_prompt("greeting")

# Get prompt template
template = await session.get_prompt_template("greeting")

# Invoke with arguments
result = await session.call_prompt(
    prompt_name="greeting",
    arguments={"name": "Alice"}
)
```

## Roots Management

### Listing Roots
```python
# Get available root directories
roots = await session.list_roots()

# Set roots callback for dynamic updates
async def roots_callback():
    return [
        {"uri": "file:///home/user/project1", "name": "Project 1"},
        {"uri": "file:///home/user/project2", "name": "Project 2"}
    ]

session.set_roots_callback(roots_callback)
```

## Pagination

### Client-Side Pagination
```python
# Pagination is handled automatically by the SDK
# For manual control:

resources = await session.list_resources()
while True:
    # Process current page
    for resource in resources.resources:
        print(resource.uri)
    
    # Check if more pages
    if resources.next_cursor:
        resources = await session.list_resources(cursor=resources.next_cursor)
    else:
        break
```

## Error Handling

### Common Errors
```python
from mcp import MCPError, InvalidRequestError, InternalError

async def safe_tool_call(session, tool_name, arguments):
    try:
        result = await session.call_tool(tool_name, arguments)
        return result
    except InvalidRequestError as e:
        print(f"Invalid request: {e}")
    except InternalError as e:
        print(f"Internal error: {e}")
    except MCPError as e:
        print(f"MCP error: {e}")
```

### Cancellation
```python
import mcp.types as types

async def cancel_request(session, request_id):
    """Cancel a previously-issued request."""
    await session.send_notification(
        types.ClientNotification(
            types.CancelledNotification(
                params=types.CancelledNotificationParams(
                    requestId=request_id,
                    reason="User navigated away"
                )
            )
        )
    )
```

## Logging

### Client-Side Logging
```python
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)

# Or use the SDK's logging
session.set_logging_level("debug")
```

## Display Utilities

### Human-Display Format
```python
from mcp.client.util import display_content

# Display content in a human-readable format
result = await session.call_tool("add", {"a": 1, "b": 2})
for content in result.content:
    print(display_content(content))
```

## Connection Management

### Checking Connection Status
```python
# Check if session is ready to send
if session.can_send():
    await session.send_request(method, params)

# Check if session is closed
if session.is_closed():
    print("Session is closed")
```

### Graceful Shutdown
```python
async with ClientSession(transport) as session:
    try:
        # Use session
        pass
    finally:
        # Session closes automatically when exiting context
        pass
```

## OAuth Authentication

### OAuth 2.1 Support
```python
# Configure OAuth for a resource
await session.request_oauth_completion(
    server_name="example",
    client_id="client-id",
    scopes=["read", "write"],
    authorization_endpoint="https://example.com/oauth/authorize",
    token_endpoint="https://example.com/oauth/token"
)
```

## Common Patterns

### Async Context Manager
```python
async with ClientSession(transport) as session:
    await session.initialize()
    
    # List tools
    tools = await session.list_tools()
    
    # Call a tool
    result = await session.call_tool("tool_name", {"arg": "value"})
    
    # Read a resource
    resource = await session.read_resource("uri://resource")
```

### Event Loop Integration
```python
import asyncio

async def main():
    transport = StdioClientTransport(command="python", args=["server.py"])
    async with ClientSession(transport) as session:
        await session.initialize()
        tools = await session.list_tools()
        print(f"Available tools: {[t.name for t in tools.tools]}")

if __name__ == "__main__":
    asyncio.run(main())
```
