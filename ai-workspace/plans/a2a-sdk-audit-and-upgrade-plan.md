# A2A SDK Audit and Upgrade Plan

**Date**: 2026-04-25  
**Project**: RAG Pipeline  
**Current Mode**: Architect  
**Status**: Planning Phase

---

## Executive Summary

This document outlines the findings from auditing the current A2A implementation against the official A2A Python SDK v1.0 documentation. The audit reveals several critical issues that require updates to ensure compatibility with the latest SDK version and proper A2A protocol compliance.

---

## 1. Current State Analysis

### 1.1 Dependencies

**File**: [`pyproject.toml`](../apps/api/pyproject.toml:30)

```toml
"a2a-sdk",  # No version pinning - RISK
```

**Issues**:
- No version pinning exposes the project to breaking changes
- Cannot verify which version is currently installed
- Dependency resolution may be inconsistent across environments

### 1.2 A2A Server Implementation

**Files**: 
- [`a2a_audit_server.py`](../apps/api/src/agents/a2a_audit_server.py:1)
- [`a2a_correction_server.py`](../apps/api/src/agents/a2a_correction_server.py:1)

**Current Implementation**:
```python
from a2a.server import A2AServer, TaskHandler
from a2a.types import SendMessageRequest, Task, TaskState
```

**Issues**:
- `A2AServer` is imported but never instantiated or registered
- No routes are created for the A2A endpoints
- Server is not mounted in [`main.py`](../apps/api/src/main.py:1)

### 1.3 A2A Client Implementation

**File**: [`a2a_loop_orchestrator.py`](../apps/api/src/agents/a2a_loop_orchestrator.py:5)

**Current Implementation**:
```python
from a2a.client import A2AClient
```

**Issues**:
- Client is created with simple URL string: `A2AClient(url=f"{base_url}/a2a/audit")`
- No `ClientConfig` is provided
- Missing proper client factory pattern

### 1.4 Type Usage Inconsistencies

**File**: [`test_a2a_helpers.py`](../apps/api/tests/test_a2a_helpers.py:51)

**Current**:
```python
status = make_task_status(TaskState.working)  # INCORRECT
```

**Should be** (per SDK v1.0):
```python
status = make_task_status(TaskState.TASK_STATE_WORKING)  # CORRECT
```

**All TaskState enum values** (per SDK v1.0):
- `TASK_STATE_UNSPECIFIED`
- `TASK_STATE_SUBMITTED`
- `TASK_STATE_WORKING`
- `TASK_STATE_COMPLETED`
- `TASK_STATE_FAILED`
- `TASK_STATE_CANCELED`
- `TASK_STATE_INPUT_REQUIRED`
- `TASK_STATE_AUTH_REQUIRED`
- `TASK_STATE_REJECTED`

### 1.5 Missing A2A Server Routes

**File**: [`main.py`](../apps/api/src/main.py:68)

**Current**:
```python
app.include_router(a2a_discovery.router, tags=["a2a-discovery"])
```

**Missing**:
- A2A JSON-RPC routes for `/a2a/audit` and `/a2a/correction`
- Server instances are never created or mounted

---

## 2. Latest A2A SDK Version

### 2.1 SDK Version Information

Based on the documentation at [`a2a-python-sdk-complete-rag.md`](../ai-workspace/docs/A2A/v1/a2a-python-sdk-complete-rag.md):

- **SDK Name**: `a2a-sdk`
- **Latest Version**: v1.0 (as per documentation)
- **Python Requirement**: 3.10+
- **Available Extras**:
  - `http-server` - HTTP Server support
  - `grpc` - gRPC support
  - `telemetry` - OpenTelemetry tracing
  - `encryption` - Encryption
  - `all` - All extras

### 2.2 Recommended Version Pin

```toml
"a2a-sdk>=1.0.0,<2.0.0"  # Or specific version if available
```

---

## 3. Required Changes

### 3.1 Dependency Updates

**File**: [`pyproject.toml`](../apps/api/pyproject.toml:30)

**Change**:
```diff
-    "a2a-sdk",
+    "a2a-sdk>=1.0.0,<2.0.0",
```

**Action**: Pin to version 1.0.0 or latest stable

---

### 3.2 Server Implementation

**New File**: `src/agents/a2a_servers.py`

**Purpose**: Create and configure A2A server instances

**Content**:
```python
"""A2A Protocol v1.0 server instances for Audit and Correction agents."""

from a2a.server import A2AServer
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_jsonrpc_routes

from src.agents.a2a_audit_server import AuditTaskHandler
from src.agents.a2a_correction_server import CorrectionTaskHandler
from src.agents.a2a_agent_cards import build_audit_agent_card, build_correction_agent_card


def create_audit_server(base_url: str) -> A2AServer:
    """Create and configure the Audit Agent server."""
    agent_card = build_audit_agent_card(base_url)
    handler = DefaultRequestHandler(
        agent_executor=AuditTaskHandler(),
        task_store=None,  # Use default InMemoryTaskStore
        agent_card=agent_card,
    )
    routes = create_jsonrpc_routes(
        request_handler=handler,
        rpc_url="/a2a/audit",
        enable_v0_3_compat=False,
    )
    return A2AServer(routes=routes, agent_card=agent_card)


def create_correction_server(base_url: str) -> A2AServer:
    """Create and configure the Correction Agent server."""
    agent_card = build_correction_agent_card(base_url)
    handler = DefaultRequestHandler(
        agent_executor=CorrectionTaskHandler(),
        task_store=None,  # Use default InMemoryTaskStore
        agent_card=agent_card,
    )
    routes = create_jsonrpc_routes(
        request_handler=handler,
        rpc_url="/a2a/correction",
        enable_v0_3_compat=False,
    )
    return A2AServer(routes=routes, agent_card=agent_card)
```

---

### 3.3 Main Application Updates

**File**: [`main.py`](../apps/api/src/main.py)

**Changes**:

1. Import server creation functions
2. Create server instances in lifespan
3. Mount server routes

```python
# Add to imports
from src.agents.a2a_servers import create_audit_server, create_correction_server

# Add to lifespan
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
    # Create A2A servers
    base_url = app.state.config.a2a_base_url  # From config
    audit_server = create_audit_server(base_url)
    correction_server = create_correction_server(base_url)
    
    # Mount server routes
    app.mount("/a2a/audit", audit_server.app)
    app.mount("/a2a/correction", correction_server.app)
    
    async with mcp_lifespan():
        yield
```

---

### 3.4 Configuration Updates

**File**: [`config.py`](../apps/api/src/config.py)

**Add**:
```python
class Settings(BaseSettings):
    # ... existing settings ...
    
    A2A_BASE_URL: str = Field(default="http://localhost:8000")
    A2A_STREAMING_ENABLED: bool = Field(default=True)
    A2A_PUSH_NOTIFICATIONS_ENABLED: bool = Field(default=False)
```

---

### 3.5 Client Configuration Updates

**File**: [`a2a_loop_orchestrator.py`](../apps/api/src/agents/a2a_loop_orchestrator.py)

**Current**:
```python
from a2a.client import A2AClient

audit_client = A2AClient(url=f"{base_url}/a2a/audit")
```

**Should be**:
```python
from a2a.client import A2AClient, ClientConfig

config = ClientConfig(
    streaming=True,
    polling=False,
    supported_protocol_bindings=["JSONRPC", "HTTP+JSON"],
    accepted_output_modes=["text", "data", "file"],
)

audit_client = A2AClient(url=f"{base_url}/a2a/audit", config=config)
```

---

### 3.6 Type Usage Fixes

**Files to Update**:
- [`a2a_audit_server.py`](../apps/api/src/agents/a2a_audit_server.py)
- [`a2a_correction_server.py`](../apps/api/src/agents/a2a_correction_server.py)
- [`a2a_loop_orchestrator.py`](../apps/api/src/agents/a2a_loop_orchestrator.py)
- [`a2a_helpers.py`](../apps/api/src/agents/a2a_helpers.py)
- [`test_a2a_helpers.py`](../apps/api/tests/test_a2a_helpers.py)

**Change all**:
```diff
- TaskState.working
- TaskState.completed
- TaskState.failed
+ TaskState.TASK_STATE_WORKING
+ TaskState.TASK_STATE_COMPLETED
+ TaskState.TASK_STATE_FAILED
```

---

### 3.7 Agent Card URL Updates

**File**: [`a2a_agent_cards.py`](../apps/api/src/agents/a2a_agent_cards.py)

**Current**:
```python
url=f"{base_url}/a2a/audit",  # Missing .well-known path
```

**Should be** (per A2A spec):
```python
url=f"{base_url}/a2a/audit/.well-known/agent-card.json",
```

Or use the discovery endpoint:
```python
url=f"{base_url}/a2a/audit",  # Server will redirect to .well-known
```

---

## 4. Testing Requirements

### 4.1 Unit Tests

Update existing tests to use correct enum values:
- [`test_a2a_helpers.py`](../apps/api/tests/test_a2a_helpers.py)

### 4.2 Integration Tests

**New Tests to Add**:
1. Test A2A server startup and route registration
2. Test A2A client connection to server
3. Test full audit-correct loop with A2A protocol
4. Test error handling and task cancellation
5. Test streaming support

---

## 5. Migration Steps

### Phase 1: Dependency Update
1. Pin `a2a-sdk` version in `pyproject.toml`
2. Run `uv sync` to install
3. Verify no breaking changes in imports

### Phase 2: Type Fixes
1. Update all `TaskState` enum usage
2. Update all `Role` enum usage
3. Run tests to verify

### Phase 3: Server Implementation
1. Create `a2a_servers.py`
2. Update `main.py` to mount servers
3. Update `config.py` with A2A settings
4. Test server endpoints

### Phase 4: Client Configuration
1. Update `a2a_loop_orchestrator.py` with `ClientConfig`
2. Test client-server communication
3. Verify protocol compliance

### Phase 5: Testing
1. Update unit tests
2. Add integration tests
3. Run full test suite

---

## 6. Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking changes in SDK | High | Pin version, test thoroughly |
| Missing server routes | Critical | Add routes before production |
| Type mismatches | Medium | Update all enum usage |
| Configuration drift | Low | Use centralized config |

---

## 7. Traefik Reverse Proxy Configuration

### 7.1 Current Traefik Setup

**File**: [`traefik-config.yml`](../infra/traefik-config.yml:1)

**Current Routers**:
```yaml
http:
  routers:
    api:
      rule: "PathPrefix(`/api`)"
      service: api
    web:
      rule: "PathPrefix(`/`)"
      service: web
      priority: 1
```

**Issue**: The `/api` prefix rule will catch `/api/v1/*` but A2A endpoints are at `/a2a/audit` and `/a2a/correction` which are NOT under `/api/v1`.

### 7.2 Required Traefik Configuration Changes

**File**: [`traefik-config.yml`](../infra/traefik-config.yml:1)

**Add A2A Routers**:
```yaml
http:
  routers:
    # ... existing routers ...
    
    # A2A Audit Agent
    a2a-audit:
      rule: "PathPrefix(`/a2a/audit`)"
      service: a2a-audit
      entryPoints:
        - web
      priority: 2  # Higher priority than api router
    
    # A2A Correction Agent
    a2a-correction:
      rule: "PathPrefix(`/a2a/correction`)"
      service: a2a-correction
      entryPoints:
        - web
      priority: 2
    
    # ... rest of routers ...
```

**Add A2A Services**:
```yaml
  services:
    # ... existing services ...
    
    a2a-audit:
      loadBalancer:
        servers:
          - url: "http://api:8000"
        healthCheck:
          path: "/a2a/audit/.well-known/agent-card.json"
    
    a2a-correction:
      loadBalancer:
        servers:
          - url: "http://api:8000"
        healthCheck:
          path: "/a2a/correction/.well-known/agent-card.json"
```

### 7.3 Docker Compose Labels for A2A Services

**File**: [`docker-compose.yml`](../infra/docker-compose.yml:22)

**Current API Service**:
```yaml
  api:
    labels:
      - "traefik.enable=true"
```

**Update to Include A2A Endpoints**:
```yaml
  api:
    labels:
      - "traefik.enable=true"
      # A2A Audit Agent routes
      - "traefik.http.routers.a2a-audit.rule=PathPrefix(`/a2a/audit`)"
      - "traefik.http.routers.a2a-audit.entrypoints=web"
      - "traefik.http.routers.a2a-audit.priority=2"
      - "traefik.http.services.a2a-audit.loadbalancer.server.port=8000"
      
      # A2A Correction Agent routes
      - "traefik.http.routers.a2a-correction.rule=PathPrefix(`/a2a/correction`)"
      - "traefik.http.routers.a2a-correction.entrypoints=web"
      - "traefik.http.routers.a2a-correction.priority=2"
      - "traefik.http.services.a2a-correction.loadbalancer.server.port=8000"
```

### 7.4 Traefik Configuration Strategy

**Option A: File-based Configuration (Recommended)**
- Update `traefik-config.yml` with A2A routers
- Pros: Centralized, version-controlled, easier to manage
- Cons: Requires container restart for changes

**Option B: Docker Labels**
- Add labels directly to `docker-compose.yml`
- Pros: Dynamic, no restart needed
- Cons: More verbose, scattered configuration

**Recommendation**: Use Option A (file-based) for production, Option B for development.

---

## 8. References

1. [A2A Python SDK v1.0 Documentation](../ai-workspace/docs/A2A/v1/a2a-python-sdk-complete-rag.md)
2. [A2A Protocol Specification](https://a2a-protocol.org/latest/specification/)
3. [a2a-python-sdk GitHub](https://github.com/a2aproject/a2a-python-sdk)
4. [Traefik Documentation](https://doc.traefik.io/traefik/)

---

## 9. Appendix

### 9.1 Current File Structure

```
rag-pipline/apps/api/
├── src/
│   ├── agents/
│   │   ├── a2a_audit_server.py      # TaskHandler only
│   │   ├── a2a_correction_server.py # TaskHandler only
│   │   ├── a2a_agent_cards.py       # AgentCard builders
│   │   ├── a2a_helpers.py           # Helper functions
│   │   └── a2a_loop_orchestrator.py # Client orchestrator
│   ├── routers/
│   │   └── a2a_discovery.py         # AgentCard discovery
│   └── main.py                      # App entry point
└── pyproject.toml                   # Dependencies
```

### 9.2 New File Structure (After Changes)

```
rag-pipline/apps/api/
├── src/
│   ├── agents/
│   │   ├── a2a_audit_server.py      # TaskHandler only
│   │   ├── a2a_correction_server.py # TaskHandler only
│   │   ├── a2a_agent_cards.py       # AgentCard builders
│   │   ├── a2a_helpers.py           # Helper functions
│   │   ├── a2a_loop_orchestrator.py # Client orchestrator
│   │   └── a2a_servers.py           # NEW: Server instances
│   ├── routers/
│   │   └── a2a_discovery.py         # AgentCard discovery
│   └── main.py                      # App entry point (updated)
└── pyproject.toml                   # Dependencies (updated)
```

### 9.3 Traefik Configuration Files

```
rag-pipline/infra/
├── docker-compose.yml           # Service definitions (updated)
├── traefik-config.yml          # Traefik routers/services (updated)
└── traefik/
    └── config/                 # Traefik configuration directory
```

---

**Document Status**: Draft
**Next Steps**: Review and approval for implementation
