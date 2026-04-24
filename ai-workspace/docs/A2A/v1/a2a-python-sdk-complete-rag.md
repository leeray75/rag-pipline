# A2A Python SDK v1.0 - Complete RAG-Optimized Documentation

## Overview

**A2A Python SDK v1.0** is a production-ready library for building agentic applications that comply with the Agent2Agent (A2A) Protocol specification v1.0. The SDK enables interoperability between AI agents through standardized communication protocols.

## Installation

```bash
# Core SDK
pip install a2a-sdk

# With extras
pip install "a2a-sdk[http-server]"    # HTTP Server support
pip install "a2a-sdk[grpc]"           # gRPC support
pip install "a2a-sdk[telemetry]"      # OpenTelemetry tracing
pip install "a2a-sdk[encryption]"     # Encryption
pip install "a2a-sdk[all]"            # All extras
```

## Prerequisites

- Python 3.10+
- `uv` (recommended) or `pip`

## Architecture Overview

### Key Components

| Component | Purpose |
| :--- | :--- |
| **Client** | Connects to A2A servers, sends messages, manages tasks |
| **Server** | Exposes A2A endpoints, processes requests, manages tasks |
| **AgentExecutor** | Custom agent implementation that processes tasks |
| **ContextBuilder** | Manages agent context and state |
| **TaskStore** | Persistent storage for tasks (InMemory, PostgreSQL, MySQL, SQLite, Vertex) |

### Transport Protocols

| Protocol | Transport | Serialization | Use Case |
| :--- | :--- | :--- | :--- |
| **JSON-RPC** | HTTP(S) | JSON | Simple HTTP-based interactions |
| **HTTP+JSON/REST** | HTTP(S) | JSON | RESTful endpoints with JSON payloads |
| **gRPC** | HTTP/2 | Protocol Buffers | High-performance, typed interfaces |

## Protocol Compatibility

| Spec Version | Transport | Client | Server |
| :--- | :--- | :---: | :---: |
| **1.0** | JSON-RPC | ✅ | ✅ |
| **1.0** | HTTP+JSON/REST | ✅ | ✅ |
| **1.0** | gRPC | ✅ | ✅ |
| **0.3** (compat mode) | JSON-RPC | ✅ | ✅ |
| **0.3** (compat mode) | HTTP+JSON/REST | ✅ | ✅ |
| **0.3** (compat mode) | gRPC | ✅ | ✅ |

## Core Types

### Enum Values (v1.0)

**TaskState:**
- `TASK_STATE_UNSPECIFIED`
- `TASK_STATE_SUBMITTED`
- `TASK_STATE_WORKING`
- `TASK_STATE_COMPLETED`
- `TASK_STATE_FAILED`
- `TASK_STATE_CANCELED`
- `TASK_STATE_INPUT_REQUIRED`
- `TASK_STATE_AUTH_REQUIRED`
- `TASK_STATE_REJECTED`

**Role:**
- `ROLE_UNSPECIFIED`
- `ROLE_USER`
- `ROLE_AGENT`

### Core Protocol Buffer Types

| Type | Purpose |
| :--- | :--- |
| `Task` | Task object with ID, context, status, artifacts, history |
| `Message` | Message with role, parts, metadata |
| `Part` | Text, raw bytes, URL, or structured data part |
| `Artifact` | Task output artifact with parts |
| `AgentCard` | Agent capabilities and interfaces |
| `AgentInterface` | Transport binding configuration |
| `AgentCapabilities` | Feature flags (streaming, push notifications, etc.) |
| `TaskPushNotificationConfig` | Webhook configuration for task updates |

## Helper Functions

### Message Helpers

```python
from a2a.helpers import (
    new_text_message,
    new_data_message,
    new_raw_message,
    get_message_text,
    new_message,
    new_task,
    new_task_from_user_message,
)

# Create text message
message = new_text_message(
    text="Hello",
    role=Role.ROLE_USER
)

# Create data message
message = new_data_message(
    data={"key": "value"},
    role=Role.ROLE_USER
)

# Create raw message (bytes)
message = new_raw_message(
    raw=b"image data",
    media_type="image/png",
    role=Role.ROLE_USER
)
```

### Artifact Helpers

```python
from a2a.helpers import (
    new_text_artifact,
    new_artifact,
    get_artifact_text,
)

# Create text artifact
artifact = new_text_artifact(text="Result")
```

### Status Update Helpers

```python
from a2a.helpers import (
    new_text_status_update_event,
    new_text_artifact_update_event,
)
```

## Client API

### ClientConfig

```python
from a2a.client import ClientConfig

config = ClientConfig(
    streaming=True,
    polling=False,
    httpx_client=None,
    supported_protocol_bindings=["JSONRPC", "HTTP+JSON", "GRPC"],
    accepted_output_modes=["text", "data", "file"],
    push_notification_config=None,
)
```

### ClientFactory

```python
from a2a.client import ClientFactory, ClientConfig

factory = ClientFactory(config=ClientConfig())
client = factory.create_from_url("https://agent.example.com")
```

### Client Methods

| Method | Purpose |
| :--- | :--- |
| `send_message()` | Send a message to initiate a task |
| `get_task()` | Retrieve task status and artifacts |
| `list_tasks()` | List tasks by context or status |
| `cancel_task()` | Cancel a running task |
| `get_agent_card()` | Retrieve agent capabilities |
| `get_extended_agent_card()` | Retrieve authenticated extended capabilities |
| `create_context()` | Create a new conversation context |
| `list_contexts()` | List available contexts |

## Server API

### AgentExecutor Interface

```python
from abc import ABC, abstractmethod
from a2a.server.agent_execution import RequestContext
from a2a.server.events import EventQueue

class AgentExecutor(ABC):
    @abstractmethod
    async def execute(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        """Execute the agent's logic for a given request context."""
    
    @abstractmethod
    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        """Request the agent to cancel an ongoing task."""
```

### Request Handler

```python
from a2a.server.request_handlers import DefaultRequestHandler

handler = DefaultRequestHandler(
    agent_executor=MyAgentExecutor(),
    task_store=InMemoryTaskStore(),
    agent_card=agent_card,
)
```

### Route Creation

```python
from a2a.server.routes import create_jsonrpc_routes

routes = create_jsonrpc_routes(
    request_handler=handler,
    rpc_url="/api/a2a",
    enable_v0_3_compat=False,
)
```

## Task States

| State | Description |
| :--- | :--- |
| `TASK_STATE_SUBMITTED` | Task received, waiting to start |
| `TASK_STATE_WORKING` | Task is being processed |
| `TASK_STATE_COMPLETED` | Task completed successfully |
| `TASK_STATE_FAILED` | Task failed |
| `TASK_STATE_CANCELED` | Task was canceled |
| `TASK_STATE_INPUT_REQUIRED` | Agent needs user input |
| `TASK_STATE_AUTH_REQUIRED` | Agent needs authentication |
| `TASK_STATE_REJECTED` | Task was rejected |

## Error Handling

### A2A Errors

| Error | Description |
| :--- | :--- |
| `TaskNotFoundError` | Task not found |
| `TaskNotCancelableError` | Task cannot be canceled |
| `PushNotificationNotSupportedError` | Push notifications not supported |
| `UnsupportedOperationError` | Operation not supported |
| `ContentTypeNotSupportedError` | Content type incompatible |
| `InternalError` | Internal server error |
| `InvalidAgentResponseError` | Invalid agent response |
| `ExtendedAgentCardNotConfiguredError` | Extended card not configured |
| `InvalidParamsError` | Invalid parameters |
| `InvalidRequestError` | Invalid request |
| `MethodNotFoundError` | Method not found |
| `ExtensionSupportRequiredError` | Extension support required |

## Security Schemes

| Scheme | Purpose |
| :--- | :--- |
| `APIKeySecurityScheme` | API key authentication |
| `HTTPAuthSecurityScheme` | HTTP authentication |
| `OAuth2SecurityScheme` | OAuth 2.0 authentication |
| `OpenIdConnectSecurityScheme` | OpenID Connect |
| `MutualTlsSecurityScheme` | Mutual TLS |

## Common Workflows

### Basic Task Execution

1. Client sends `SendMessage` request
2. Server creates task and returns `Task` object
3. Client polls `GetTask` for status
4. Server returns completed task with artifacts

### Streaming Task Execution

1. Client sends `SendMessage` with streaming request
2. Server sends `TaskStatusUpdateEvent` via SSE (JSON-RPC) or streaming (gRPC/HTTP)
3. Client receives real-time updates until task completion

### Multi-Turn Interaction

1. Client sends `SendMessage` with context
2. Server returns task with `TASK_STATE_INPUT_REQUIRED` or `TASK_STATE_AUTH_REQUIRED`
3. Client provides additional input via `SendMessage` with same context
4. Server continues processing and returns final result

## Protocol Versioning

- Version format: `Major.Minor` (e.g., "1.0")
- Patch versions do not affect protocol compatibility
- Clients should request specific versions to avoid losing functionality

## File Exchange

- Files uploaded as raw bytes in artifacts
- Supported media types declared in `Artifact.mediaType`
- File size limits enforced by server implementation

## Extensions

Extensions allow agents to declare additional functionality:
- Optional or required extensions
- Versioned extension support
- Backward compatible protocol evolution

## SDK Structure

```
a2a/
├── client/           # Client-side components
│   ├── auth/         # Authentication
│   ├── base_client.py
│   ├── card_resolver.py
│   ├── client.py
│   ├── client_factory.py
│   ├── errors.py
│   ├── interceptors.py
│   └── transports/   # Transport implementations
├── server/           # Server-side components
│   ├── agent_execution/
│   ├── events/
│   ├── request_handlers/
│   ├── routes/
│   ├── tasks/
│   ├── context.py
│   ├── models.py
│   └── jsonrpc_models.py
├── types/            # Protocol Buffer types
│   ├── a2a_pb2.py
│   ├── a2a_pb2.pyi
│   └── __init__.py
├── helpers/          # Helper functions
│   ├── agent_card.py
│   └── proto_helpers.py
└── utils/            # Utility functions
    ├── errors.py
    └── task.py
```

## References

- **Protocol Spec**: https://a2a-protocol.org/latest/specification/
- **Samples**: https://github.com/a2aproject/a2a-samples
- **Inspector**: https://github.com/a2aproject/a2a-inspector
- **DeepLearning.AI Course**: https://goo.gle/dlai-a2a
