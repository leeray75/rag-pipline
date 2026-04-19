# Model Context Protocol - Transport Layer Specification

## Overview

The Model Context Protocol (MCP) defines two standard transport mechanisms for communication between clients and servers:

1. **stdio** - Traditional stdin/stdout pipe communication
2. **Streamable HTTP** - HTTP-based transport with connection management

## Transport Security Warnings

### stdio Transport
- **Appropriate for local processes** only
- **Not secure for network communication**
- No built-in encryption
- Should only be used when client and server run on the same host

### Streamable HTTP Transport
- **Designed for network communication**
- Supports HTTPS for encryption
- Provides session management
- Supports connection resumption

## Message Sending Pattern

Both transports follow a consistent pattern:

```python
# Sending a request
result = await session.send_request(method, params)

# Receiving and processing messages
async for message in session:
    # Process incoming messages
    pass
```

## Session Management

### Connection Termination
- Either side can close the connection at any time
- The `on_event("close")` callback fires when the connection closes
- The `session.is_closed()` method indicates connection state
- If the remote side closes, local code should also close

### Message Sending Rules
- Can only send messages after initial handshake completes
- Before handshake: `session.can_send()` returns `False`
- After handshake: `session.can_send()` returns `True`
- Sending before handshake raises `RuntimeError`

### Session Closure
```python
# Graceful closure
await session.close()

# Check status before sending
if session.can_send():
    await session.send_request(method, params)

# Listen for closure events
async def on_close():
    print("Connection closed")

session.on_event("close", on_close)
```

## Streamable HTTP Transport Details

### Connection Handshake
- Uses the `MCP-Session-Id` HTTP header
- Server generates unique session ID on first request
- Client includes this ID in subsequent requests
- If no ID provided, server creates new session

### Resumability
- Supports resuming interrupted connections
- Uses the `Last-Event-ID` header for resumption
- Server stores pending messages for a time window
- Client can resume from last received event

### Heartbeat Mechanism
- Servers can send heartbeat messages
- Clients respond to maintain connection
- Prevents connection timeouts

## Protocol Version Negotiation

Both transports support protocol version negotiation:
- Client sends `LATEST_PROTOCOL_VERSION` during initialization
- Server responds with supported version
- If incompatible, client raises `RuntimeError`
- Versions are defined in `mcp.shared.version`

## Backwards Compatibility

- New protocol versions are backwards compatible
- Older clients can still connect to newer servers
- Protocol evolution is carefully managed
- Breaking changes require version updates

## Implementation Examples

### stdio Transport
```python
from mcp import StdioServerTransport
from my_server import create_server

transport = StdioServerTransport()
server = create_server()
await server.run(transport)
```

### Streamable HTTP Transport
```python
from mcp import ServerSession
from mcp.types import HTTPResponse

async def handle_request(request):
    session = ServerSession()
    response = HTTPResponse(status=200, headers={})
    
    if request.headers.get("MCP-Session-Id"):
        # Resuming existing session
        session.resume(request.headers["MCP-Session-Id"])
    else:
        # New session
        session_id = session.create()
        response.headers["MCP-Session-Id"] = session_id
    
    return response
```

## Key Takeaways

1. Use **stdio** for local, same-host communication only
2. Use **Streamable HTTP** for network-based or remote communication
3. Always check `session.can_send()` before sending messages
4. Handle connection closures gracefully with event callbacks
5. Session IDs enable resumability for HTTP transport
6. Protocol version negotiation ensures compatibility
7. Neither transport is secure by default - use HTTPS for network communication
