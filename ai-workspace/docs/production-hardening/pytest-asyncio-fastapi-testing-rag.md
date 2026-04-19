# pytest-asyncio + FastAPI Testing — RAG Reference Document

<!-- RAG_METADATA
topic: testing, async-testing, fastapi, mcp
library: pytest, pytest-asyncio, httpx
version: pytest-asyncio 0.24+, httpx 0.27+
python_min: 3.9
tags: pytest, pytest-asyncio, httpx, fastapi, async-tests, mcp-testing, jwt-testing, url-validator, health-checks, reingestion
use_case: phase-7-subtask-5-tests-validation
-->

## Overview

**pytest-asyncio** enables testing of `async` functions with pytest. **httpx** provides an `AsyncClient` for testing FastAPI apps without starting a real server.

**Install** (dev dependencies):
```bash
pip install pytest pytest-asyncio httpx
```

**Key versions**: pytest-asyncio 0.24+ changed the default mode to `strict`. Configure in `pyproject.toml`.

---

## Configuration (`pyproject.toml`)

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"          # Auto-detect async test functions
testpaths = ["tests"]
python_files = ["test_*.py"]
python_functions = ["test_*"]

# OR use strict mode (requires @pytest.mark.asyncio on each test)
# asyncio_mode = "strict"
```

**`asyncio_mode = "auto"`** — All `async def test_*` functions are automatically treated as async tests. No need for `@pytest.mark.asyncio` decorator.

**`asyncio_mode = "strict"`** — Requires explicit `@pytest.mark.asyncio` on each async test.

---

## Basic Async Test Pattern

```python
import pytest

@pytest.mark.asyncio
async def test_some_async_code():
    result = await some_async_function()
    assert result == "expected"

# With asyncio_mode = "auto", the decorator is optional:
async def test_some_async_code_auto():
    result = await some_async_function()
    assert result == "expected"
```

---

## FastAPI Testing with `httpx.AsyncClient`

```python
import pytest
from httpx import AsyncClient
from src.main import app


@pytest.mark.asyncio
async def test_health_endpoint():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_post_endpoint():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/jobs",
            json={"url": "https://docs.python.org/3/"},
        )
    assert response.status_code == 201
    body = response.json()
    assert "job_id" in body
```

**Important**: Use `AsyncClient(app=app, base_url="http://test")` — the `base_url` must be a valid URL but doesn't need to be reachable. The `app` parameter routes requests directly to the FastAPI app without network I/O.

---

## MCP Server Tests

```python
"""Tests for the MCP server tool registration."""
import pytest
from src.mcp.server import mcp


@pytest.mark.asyncio
async def test_list_tools_returns_all_tools():
    """All 7 MCP tools are registered."""
    from mcp.types import ListToolsRequest

    result = await mcp.handle_request(
        ListToolsRequest(method="tools/list", params={})
    )
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

    result = await mcp.handle_request(
        ListToolsRequest(method="tools/list", params={})
    )
    for tool in result.tools:
        assert tool.inputSchema is not None
        assert "type" in tool.inputSchema
        assert tool.inputSchema["type"] == "object"
        assert "properties" in tool.inputSchema
```

**Critical**: Use `mcp.handle_request(ListToolsRequest(...))` — the public MCP SDK API. Do NOT use `mcp._tool_handlers["list_tools"]()` — this accesses an internal dict that is an implementation detail subject to change.

---

## MCP HTTP Transport Tests

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

---

## JWT Auth Tests

```python
"""Tests for JWT authentication."""
import pytest
from datetime import timedelta
from src.auth.jwt import create_access_token, decode_token


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

---

## URL Validator / SSRF Tests

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

---

## Async Fixtures

```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

@pytest.fixture
async def db_session():
    """Async database session for tests."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    AsyncTestSession = async_sessionmaker(engine, class_=AsyncSession)
    async with AsyncTestSession() as session:
        yield session
    
    await engine.dispose()


@pytest.fixture
async def client():
    """Async HTTP client for FastAPI tests."""
    async with AsyncClient(app=app, base_url="http://test") as c:
        yield c
```

---

## Running Tests

```bash
# Run all tests
cd rag-pipeline/apps/api && python -m pytest tests/ -v

# Run specific test files
python -m pytest tests/test_mcp_server.py tests/test_auth.py -v

# Run by keyword
python -m pytest -k "mcp or auth or url_validator" -v

# Run with coverage
python -m pytest tests/ --cov=src --cov-report=term-missing

# Run with verbose output and stop on first failure
python -m pytest tests/ -v -x
```

---

## `conftest.py` Pattern

```python
# tests/conftest.py
import os
import pytest

# Disable external services in tests
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ.pop("SENTRY_DSN", None)
os.environ["OTEL_ENABLED"] = "false"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"
```

---

## Common Pitfalls

1. **`asyncio_mode` not configured** — Without `asyncio_mode = "auto"` in `pyproject.toml`, async tests require `@pytest.mark.asyncio` on every test function.
2. **`AsyncClient` context manager** — Always use `async with AsyncClient(...) as client:`. Don't create the client outside a context manager.
3. **`base_url` required** — `AsyncClient(app=app)` without `base_url` raises an error. Use `base_url="http://test"`.
4. **MCP internal API** — Never use `mcp._tool_handlers` — it's an internal dict. Use `mcp.handle_request(ListToolsRequest(...))`.
5. **Test isolation** — Disable LangSmith, Sentry, and OTel in `conftest.py` to prevent test data from being sent to external services.
6. **`pytest.raises` context** — Use `with pytest.raises(ExceptionType) as exc_info:` and check `exc_info.value` for exception details.

---

## Sources
- https://pytest-asyncio.readthedocs.io/en/latest/ (pytest-asyncio docs)
- https://www.python-httpx.org/async/ (httpx async client)
- https://fastapi.tiangolo.com/tutorial/testing/ (FastAPI testing guide)
- https://docs.pytest.org/en/stable/ (pytest docs)
