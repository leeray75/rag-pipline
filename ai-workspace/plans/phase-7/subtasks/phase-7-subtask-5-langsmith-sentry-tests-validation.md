# Phase 7, Subtask 5 — Tests & Phase Validation

> **Phase**: Phase 7 — MCP Server, Observability & Production Hardening
> **Prerequisites**: Phase 6 complete; Phase 7 Subtasks 1-4 complete (dependencies installed, MCP server working via Streamable HTTP at `POST /mcp`, observability configured, auth & security in place, production hardening done)
> **Scope**: Comprehensive integration tests and full Phase 7 Done-When validation

> **Note**: This subtask uses only open-source, self-hosted, free tools. LangSmith (paid SaaS) and Sentry (paid SaaS) have been removed. Agent run observability is provided by OpenTelemetry → Grafana Tempo (already configured in Subtask 2). Error tracking is provided by structlog JSON logs → Grafana Loki + Prometheus `rag_jobs_failed_total` counter (already configured in Subtask 2).

---

## Relevant Technology Stack

| Package | Version | Install |
|---|---|---|
| pytest | (dev dep) | Already installed |
| pytest-asyncio | (dev dep) | Already installed |
| httpx | (dev dep) | Already installed — required for async FastAPI test client |

> Python packages were added to `pyproject.toml` in Subtask 1.

---

## Files to Create/Modify

| Action | File Path |
|---|---|
| Create | `rag-pipeline/apps/api/tests/test_mcp_server.py` |
| Create | `rag-pipeline/apps/api/tests/test_mcp_http_transport.py` |
| Create | `rag-pipeline/apps/api/tests/test_auth.py` |
| Create | `rag-pipeline/apps/api/tests/test_url_validator.py` |
| Create | `rag-pipeline/apps/api/tests/test_health.py` |
| Create | `rag-pipeline/apps/api/tests/test_reingestion.py` |

---

## Step 1: Write Integration Tests

**Working directory**: `rag-pipeline/apps/api/`

### 1.1 Create `tests/test_mcp_server.py`

Tests the MCP tool registration using the public MCP SDK API rather than internal implementation details.

> **Important**: Do NOT use `mcp._tool_handlers["list_tools"]()` — this accesses an internal dict that is an implementation detail subject to change across SDK versions. Use `mcp.handle_request()` with the public `ListToolsRequest` type instead.

```python
"""Tests for the MCP server tool registration."""

import pytest

from src.mcp.server import mcp


@pytest.mark.asyncio
async def test_list_tools_returns_all_tools():
    """All 7 MCP tools are registered."""
    from mcp.types import ListToolsRequest

    result = await mcp.handle_request(ListToolsRequest(method="tools/list", params={}))
    tool_names = {t.name for t in result.tools}
    expected = {
        "ingest_url",
        "get_job_status",
        "list_documents",
        "get_audit_report",
        "search_knowledge_base",
        "approve_job",
        "get_collection_stats",
    }
    assert tool_names == expected


@pytest.mark.asyncio
async def test_tool_schemas_have_required_fields():
    """Each tool has a valid inputSchema with required fields."""
    from mcp.types import ListToolsRequest

    result = await mcp.handle_request(ListToolsRequest(method="tools/list", params={}))
    for tool in result.tools:
        assert tool.inputSchema is not None
        assert "type" in tool.inputSchema
        assert tool.inputSchema["type"] == "object"
        assert "properties" in tool.inputSchema
```

### 1.2 Create `tests/test_mcp_http_transport.py`

End-to-end tests for the Streamable HTTP endpoint at `POST /mcp`.

```python
"""Integration tests for the MCP Streamable HTTP endpoint."""

import pytest
from httpx import AsyncClient

from src.main import app


@pytest.mark.asyncio
async def test_mcp_endpoint_lists_tools():
    """POST /mcp with tools/list returns all 7 tools."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        )
    assert response.status_code == 200
    body = response.json()
    assert "result" in body
    tool_names = {t["name"] for t in body["result"]["tools"]}
    assert "ingest_url" in tool_names
    assert "search_knowledge_base" in tool_names
    assert len(tool_names) == 7


@pytest.mark.asyncio
async def test_mcp_endpoint_rejects_unknown_method():
    """POST /mcp with an unknown JSON-RPC method returns an error."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 2, "method": "not/a/method", "params": {}},
        )
    # JSON-RPC errors are returned in the body, not always as HTTP error codes
    assert response.status_code in (200, 400)
    body = response.json()
    assert "error" in body or response.status_code == 400
```

### 1.3 Create `tests/test_auth.py`

```python
"""Tests for JWT authentication."""

import pytest
from datetime import timedelta

from src.auth.jwt import create_access_token, decode_token, TokenPayload


def test_create_and_decode_token():
    """Token can be created and decoded."""
    token = create_access_token(subject="test@example.com", role="admin")
    payload = decode_token(token)
    assert payload.sub == "test@example.com"
    assert payload.role == "admin"


def test_expired_token():
    """Expired token raises HTTPException."""
    from fastapi import HTTPException

    token = create_access_token(
        subject="test@example.com",
        expires_delta=timedelta(seconds=-1),
    )
    with pytest.raises(HTTPException) as exc_info:
        decode_token(token)
    assert exc_info.value.status_code == 401


def test_invalid_token():
    """Garbage token raises HTTPException."""
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        decode_token("not.a.valid.token")
    assert exc_info.value.status_code == 401
```

### 1.4 Create `tests/test_url_validator.py`

```python
"""Tests for SSRF prevention."""

import pytest

from src.security.url_validator import SSRFError, validate_url


def test_valid_public_url():
    """Public URL passes validation."""
    url = validate_url("https://docs.python.org/3/")
    assert url == "https://docs.python.org/3/"


def test_blocks_private_ip():
    """Private IP range is blocked."""
    with pytest.raises(SSRFError, match="blocked IP range"):
        validate_url("http://192.168.1.1/secret")


def test_blocks_localhost():
    """Localhost is blocked."""
    with pytest.raises(SSRFError, match="blocked IP range"):
        validate_url("http://127.0.0.1/admin")


def test_blocks_non_http_scheme():
    """Non-HTTP schemes are blocked."""
    with pytest.raises(SSRFError, match="Unsupported scheme"):
        validate_url("ftp://example.com/file")


def test_blocks_missing_hostname():
    """Missing hostname is blocked."""
    with pytest.raises(SSRFError):
        validate_url("http:///path")
```

### 1.5 Create `tests/test_health.py`

```python
"""Tests for health check endpoints."""

import pytest
from httpx import AsyncClient

from src.main import app


@pytest.mark.asyncio
async def test_health_liveness():
    """GET /health always returns 200."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_health_readiness_structure():
    """GET /health/ready returns correct structure."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/health/ready")
    # 200 (ready) or 503 (degraded) depending on test environment
    assert response.status_code in (200, 503)
    body = response.json()
    assert "status" in body
    assert "checks" in body
    assert "postgres" in body["checks"]
```

### 1.6 Create `tests/test_reingestion.py`

```python
"""Tests for re-ingestion delta detection."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.ingest.reingestion import ReingestionService


def test_content_hash_is_deterministic():
    """Same content always produces the same hash."""
    svc = ReingestionService()
    h1 = svc.content_hash("hello world")
    h2 = svc.content_hash("hello world")
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex = 64 chars


def test_content_hash_differs_for_different_content():
    """Different content produces different hashes."""
    svc = ReingestionService()
    h1 = svc.content_hash("version 1")
    h2 = svc.content_hash("version 2")
    assert h1 != h2


@pytest.mark.asyncio
async def test_detect_changes_identifies_added():
    """New URLs not in DB are classified as added."""
    svc = ReingestionService()

    # Mock DB session returning no existing documents
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_result

    new_docs = [{"source_url": "https://example.com/new", "content": "new content"}]
    delta = await svc.detect_changes(job_id="job-1", new_documents=new_docs, db=mock_db)

    assert "https://example.com/new" in delta["added"]
    assert len(delta["updated"]) == 0
    assert len(delta["unchanged"]) == 0


@pytest.mark.asyncio
async def test_detect_changes_identifies_unchanged():
    """URLs with same hash are classified as unchanged."""
    svc = ReingestionService()
    content = "same content"
    existing_hash = svc.content_hash(content)

    # Mock existing document with same hash
    mock_doc = MagicMock()
    mock_doc.source_url = "https://example.com/page"
    mock_doc.content_hash = existing_hash

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_doc]
    mock_db.execute.return_value = mock_result

    new_docs = [{"source_url": "https://example.com/page", "content": content}]
    delta = await svc.detect_changes(job_id="job-1", new_documents=new_docs, db=mock_db)

    assert "https://example.com/page" in delta["unchanged"]
    assert len(delta["updated"]) == 0
    assert len(delta["added"]) == 0
```

### 1.7 Run all tests

```bash
cd rag-pipeline/apps/api && python -m pytest tests/ -v
```

---

## Step 2: Summary of `src/main.py` — No New Changes for This Subtask

This subtask only adds test files. No changes to `src/main.py` are required.

The complete `src/main.py` initialization order from previous subtasks is:

```python
# 1. Logging (Subtask 2)
from src.logging_config import configure_logging
configure_logging()

# 2. FastAPI app
app = FastAPI(...)

# 3. OpenTelemetry (Subtask 2)
from src.telemetry import configure_telemetry
configure_telemetry(app)

# 4. Prometheus metrics (Subtask 2)
from src.metrics import configure_metrics
configure_metrics(app)

# 5. Routers
from src.routers.health import router as health_router  # Subtask 4
app.include_router(health_router)
# ... other routers ...
```

---

## Step 3: Full Phase 7 Done-When Validation

Run through the complete Phase 7 Done-When checklist to verify all subtasks:

| # | Criterion | Verify |
|---|-----------|--------|
| 1 | MCP server lists 7 tools | `POST /mcp` with `tools/list` → 7 tools returned |
| 2 | MCP `search_knowledge_base` returns Qdrant results | `POST /mcp` with `tools/call` and a valid collection + query |
| 3 | Streamable HTTP transport works at `POST /mcp` | `curl -X POST localhost:8000/mcp -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'` |
| 4 | Claude Desktop can trigger ingestion via MCP | Configure `"type":"http","url":"http://localhost:8000/mcp"` and call `ingest_url` |
| 5 | Structured logging outputs JSON in production | `LOG_FORMAT=json python -m uvicorn src.main:app` → JSON output |
| 6 | OpenTelemetry traces appear in Grafana Tempo | Submit a job → view trace in Grafana Explore → Tempo |
| 7 | Prometheus metrics at `/metrics` include `rag_*` counters | `curl localhost:8000/metrics \| grep rag_` |
| 8 | Grafana dashboard shows pipeline throughput | Open http://localhost:3001 → Pipeline Throughput dashboard |
| 9 | Agent run spans visible in Grafana Tempo | Submit a job → Grafana Explore → Tempo → filter `service.name=rag-pipeline-api` |
| 10 | Error logs searchable in Grafana Loki | Trigger an error → Grafana Explore → Loki → `{job="rag-pipeline-api"} \| json \| level="error"` |
| 11 | JWT auth protects sensitive endpoints | `curl -X POST /api/v1/ingest/jobs/{id}/embed` without token → 401 |
| 12 | Rate limiting returns 429 when exceeded | Send >100 requests/min → 429 response |
| 13 | SSRF prevention blocks private IPs | Submit `http://192.168.1.1` → rejected |
| 14 | Re-ingestion detects changed documents | Re-fetch same URL with modified content → delta detected |
| 15 | Health check endpoints work | `GET /health` → 200, `GET /health/ready` → 200 or 503 |
| 16 | Docker Compose prod overlay validates | `docker compose -f docker-compose.yml -f docker-compose.prod.yml config` succeeds |
| 17 | README.md covers setup, architecture, MCP, observability | File exists with complete sections |
| 18 | Runbook covers startup, common issues, manual overrides | File exists with all scenarios |
| 19 | All Phase 7 tests pass | `pytest tests/ -v` → all pass |
| 20 | Load test: 5 concurrent jobs with 50 docs each complete | Run load test script and verify all jobs reach "ingested" |

---

## Done-When Checklist (This Subtask)

| # | Criterion | Verify |
|---|-----------|--------|
| 1 | MCP server unit tests pass | `pytest tests/test_mcp_server.py -v` → all pass |
| 2 | MCP HTTP transport integration tests pass | `pytest tests/test_mcp_http_transport.py -v` → all pass |
| 3 | Auth tests pass | `pytest tests/test_auth.py -v` → all pass |
| 4 | URL validator tests pass | `pytest tests/test_url_validator.py -v` → all pass |
| 5 | Health check tests pass | `pytest tests/test_health.py -v` → all pass |
| 6 | Re-ingestion tests pass | `pytest tests/test_reingestion.py -v` → all pass |
| 7 | Full Phase 7 Done-When checklist passes | All 20 items verified |

---

## Summary Report

Upon completion of this subtask, create a summary report at:
`rag-pipeline/ai-workspace/summary-reports/phase-7-subtask-5-tests-validation-summary.md`

The summary report must include:
- **Subtask**: Phase 7, Subtask 5 — Tests & Phase Validation
- **Status**: Complete / Partial / Blocked
- **Date**: {ISO 8601 date}
- **Files Created/Modified**: List every file path
- **Key Decisions**: Any deviations from the plan and why
- **Issues Encountered**: Problems and resolutions
- **Dependencies for Next Subtask**: N/A (final subtask of Phase 7)
- **Verification Results**: Output of Done-When checklist items
