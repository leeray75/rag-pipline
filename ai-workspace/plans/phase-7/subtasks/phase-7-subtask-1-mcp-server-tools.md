# Phase 7, Subtask 1 — MCP Server Tools

> **Phase**: Phase 7 — MCP Server, Observability & Production Hardening
> **Prerequisites**: Phase 6 complete (chunks generated, FastEmbed embeddings working, Qdrant collections populated, JSON review UI functional, similarity search verified)
> **Scope**: Add Phase 7 Python dependencies + build the full MCP server with 7 tools using the **Streamable HTTP transport** (current MCP spec standard, March 2025)

---

## Relevant Technology Stack

| Package | Version | Install |
|---|---|---|
| MCP Python SDK | 1.27.0 | `pip install mcp` |
| Python | 3.13.x | Runtime |
| FastAPI | 0.135.3 | Already installed |

---

## Files to Create/Modify

| Action | File Path |
|---|---|
| Modify | `rag-pipeline/apps/api/pyproject.toml` |
| Create | `rag-pipeline/apps/api/src/mcp/__init__.py` |
| Create | `rag-pipeline/apps/api/src/mcp/server.py` |
| Create | `rag-pipeline/apps/api/src/mcp/tool_handlers.py` |
| Create | `rag-pipeline/apps/api/src/mcp/http_transport.py` |
| Modify | `rag-pipeline/apps/api/src/main.py` |

> **Note**: `sse_transport.py` and `__main__.py` are **not created**. The legacy SSE two-endpoint pattern and stdio mode are replaced entirely by the Streamable HTTP transport.

---

## Step 1: Add Phase 7 Python Dependencies

**Working directory**: `rag-pipeline/apps/api/`

### 1.1 Update `pyproject.toml` — add to `[project.dependencies]`

```toml
[project.dependencies]
# ... existing deps from Phases 1-6 ...
mcp = ">=1.27.0,<2.0.0"
opentelemetry-api = ">=1.33.0,<2.0.0"
opentelemetry-sdk = ">=1.33.0,<2.0.0"
opentelemetry-instrumentation-fastapi = ">=0.54b0"
opentelemetry-instrumentation-celery = ">=0.54b0"
opentelemetry-instrumentation-httpx = ">=0.54b0"
opentelemetry-exporter-otlp = ">=1.33.0,<2.0.0"
prometheus-fastapi-instrumentator = ">=7.1.0,<8.0.0"
python-jose = {version = ">=3.4.0,<4.0.0", extras = ["cryptography"]}
slowapi = ">=0.1.9,<1.0.0"
structlog = ">=25.4.0,<26.0.0"
langsmith = ">=0.3.42,<1.0.0"
sentry-sdk = {version = ">=2.29.1,<3.0.0", extras = ["fastapi"]}
```

### 1.2 Install

```bash
cd rag-pipeline/apps/api && pip install -e ".[dev]"
```

**Done when**: All packages import without errors.

---

## Step 2: Create `src/mcp/__init__.py`

```python
"""MCP Server package — exposes pipeline tools to AI assistants via Streamable HTTP."""
```

---

## Step 3: Create `src/mcp/server.py`

```python
"""MCP Server — exposes RAG pipeline tools via the Model Context Protocol.

Transport: Streamable HTTP (current MCP spec standard, March 2025).
Endpoint:  POST /mcp  (single unified endpoint for all clients)

Do NOT import mcp.server.sse or mcp.server.stdio — those transports are
not used in this implementation.
"""

import logging

from mcp.server import Server
from mcp.types import TextContent, Tool

logger = logging.getLogger(__name__)

# Create the MCP server instance
mcp = Server("rag-pipeline")


@mcp.list_tools()
async def list_tools() -> list[Tool]:
    """Register all MCP tools."""
    return [
        Tool(
            name="ingest_url",
            description=(
                "Create an ingestion job from a URL. "
                "Optionally crawl all linked pages."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL to ingest documentation from",
                    },
                    "crawl_all": {
                        "type": "boolean",
                        "description": "Whether to discover and crawl all linked pages",
                        "default": False,
                    },
                },
                "required": ["url"],
            },
        ),
        Tool(
            name="get_job_status",
            description="Get the current status, progress, and round count for a job.",
            inputSchema={
                "type": "object",
                "properties": {
                    "job_id": {
                        "type": "string",
                        "description": "The job UUID",
                    },
                },
                "required": ["job_id"],
            },
        ),
        Tool(
            name="list_documents",
            description="List all documents for a job with their current status.",
            inputSchema={
                "type": "object",
                "properties": {
                    "job_id": {
                        "type": "string",
                        "description": "The job UUID",
                    },
                },
                "required": ["job_id"],
            },
        ),
        Tool(
            name="get_audit_report",
            description="Get the structured audit report JSON for a specific round.",
            inputSchema={
                "type": "object",
                "properties": {
                    "job_id": {
                        "type": "string",
                        "description": "The job UUID",
                    },
                    "round": {
                        "type": "integer",
                        "description": "Audit round number (1-based)",
                        "default": 1,
                    },
                },
                "required": ["job_id"],
            },
        ),
        Tool(
            name="search_knowledge_base",
            description=(
                "Query the Qdrant vector store and return "
                "ranked chunks with relevance scores."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language search query",
                    },
                    "collection_name": {
                        "type": "string",
                        "description": "Name of the Qdrant collection to search",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of results to return",
                        "default": 5,
                    },
                },
                "required": ["query", "collection_name"],
            },
        ),
        Tool(
            name="approve_job",
            description=(
                "Trigger human approval for a job. "
                "Starts JSON generation and embedding pipeline."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "job_id": {
                        "type": "string",
                        "description": "The job UUID to approve",
                    },
                },
                "required": ["job_id"],
            },
        ),
        Tool(
            name="get_collection_stats",
            description="Get Qdrant collection metadata and statistics.",
            inputSchema={
                "type": "object",
                "properties": {
                    "collection_name": {
                        "type": "string",
                        "description": "Name of the Qdrant collection",
                    },
                },
                "required": ["collection_name"],
            },
        ),
    ]
```

---

## Step 4: Create `src/mcp/tool_handlers.py`

```python
"""MCP tool handler implementations — bridge MCP calls to pipeline services."""

import json
import logging

from mcp.types import TextContent

from src.mcp.server import mcp

logger = logging.getLogger(__name__)


@mcp.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Route MCP tool calls to the appropriate handler."""
    handlers = {
        "ingest_url": _handle_ingest_url,
        "get_job_status": _handle_get_job_status,
        "list_documents": _handle_list_documents,
        "get_audit_report": _handle_get_audit_report,
        "search_knowledge_base": _handle_search_knowledge_base,
        "approve_job": _handle_approve_job,
        "get_collection_stats": _handle_get_collection_stats,
    }

    handler = handlers.get(name)
    if not handler:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    try:
        result = await handler(arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
    except Exception as e:
        logger.exception("MCP tool error: %s", name)
        return [TextContent(type="text", text=f"Error: {e}")]


async def _handle_ingest_url(args: dict) -> dict:
    """Create an ingestion job from a URL."""
    from src.workers.crawl_tasks import crawl_url_task

    url = args["url"]
    crawl_all = args.get("crawl_all", False)

    task = crawl_url_task.delay(url, crawl_all=crawl_all)
    return {
        "job_id": task.id,
        "url": url,
        "crawl_all": crawl_all,
        "status": "job_created",
        "message": f"Ingestion job created for {url}",
    }


async def _handle_get_job_status(args: dict) -> dict:
    """Get job status from Postgres."""
    from src.database import get_async_session
    from src.models.job import Job
    from sqlalchemy import select

    job_id = args["job_id"]
    async with get_async_session() as db:
        stmt = select(Job).where(Job.id == job_id)
        result = await db.execute(stmt)
        job = result.scalar_one_or_none()
        if not job:
            return {"error": f"Job {job_id} not found"}
        return {
            "job_id": str(job.id),
            "status": job.status,
            "progress": job.progress,
            "audit_rounds": job.audit_rounds,
            "created_at": str(job.created_at),
            "updated_at": str(job.updated_at),
        }


async def _handle_list_documents(args: dict) -> dict:
    """List all documents for a job."""
    from src.database import get_async_session
    from src.models.document import Document
    from sqlalchemy import select

    job_id = args["job_id"]
    async with get_async_session() as db:
        stmt = (
            select(Document)
            .where(Document.job_id == job_id)
            .order_by(Document.created_at)
        )
        result = await db.execute(stmt)
        docs = result.scalars().all()
        return {
            "job_id": job_id,
            "total": len(docs),
            "documents": [
                {
                    "id": str(d.id),
                    "title": d.title,
                    "source_url": d.source_url,
                    "status": d.status,
                }
                for d in docs
            ],
        }


async def _handle_get_audit_report(args: dict) -> dict:
    """Get audit report for a specific round."""
    from src.database import get_async_session
    from src.models.audit import AuditReport
    from sqlalchemy import select

    job_id = args["job_id"]
    round_num = args.get("round", 1)
    async with get_async_session() as db:
        stmt = (
            select(AuditReport)
            .where(AuditReport.job_id == job_id)
            .where(AuditReport.round_number == round_num)
        )
        result = await db.execute(stmt)
        report = result.scalar_one_or_none()
        if not report:
            return {"error": f"No audit report for job {job_id} round {round_num}"}
        return {
            "job_id": job_id,
            "round": round_num,
            "report": report.report_json,
        }


async def _handle_search_knowledge_base(args: dict) -> dict:
    """Search Qdrant collection using FastEmbed."""
    from src.ingest.qdrant_ingest import QdrantIngestService

    query = args["query"]
    collection_name = args["collection_name"]
    top_k = args.get("top_k", 5)

    service = QdrantIngestService()
    results = service.test_similarity_search(
        collection_name=collection_name,
        query_text=query,
        limit=top_k,
    )
    return {
        "query": query,
        "collection": collection_name,
        "top_k": top_k,
        "results": results,
    }


async def _handle_approve_job(args: dict) -> dict:
    """Approve a job and trigger JSON generation pipeline."""
    from src.workers.ingest_tasks import chunk_job_task

    job_id = args["job_id"]
    task = chunk_job_task.delay(job_id)
    return {
        "job_id": job_id,
        "task_id": task.id,
        "status": "approved",
        "message": "Job approved — chunking pipeline started",
    }


async def _handle_get_collection_stats(args: dict) -> dict:
    """Get Qdrant collection statistics."""
    from src.ingest.qdrant_ingest import QdrantIngestService

    collection_name = args["collection_name"]
    service = QdrantIngestService()
    return service.get_collection_stats(collection_name)
```

---

## Step 5: Create `src/mcp/http_transport.py`

This replaces the old `sse_transport.py`. It mounts the MCP server into FastAPI using the **Streamable HTTP transport** — a single `POST /mcp` endpoint. Clients send JSON-RPC requests to this endpoint; the server responds as plain JSON (non-streaming clients) or as a server-sent event stream within the same HTTP response (streaming clients), negotiated via the `Accept` header. No separate `GET /sse` or `POST /messages/` endpoints are needed.

```python
"""Streamable HTTP transport for embedding the MCP server into the FastAPI app.

The Streamable HTTP transport exposes a single endpoint:
    POST /mcp

This replaces the legacy two-endpoint SSE pattern (GET /mcp/sse + POST /mcp/messages/).
Streaming clients send Accept: text/event-stream and receive an SSE response
from within the same POST handler. Non-streaming clients receive plain JSON.

MCP spec reference:
    https://modelcontextprotocol.io/specification/2025-03-26/basic/transports
"""

import logging

from fastapi import APIRouter
from mcp.server.streamable_http import StreamableHTTPServerTransport
from starlette.requests import Request
from starlette.responses import Response

from src.mcp.server import mcp
from src.mcp.tool_handlers import call_tool  # noqa: F401 — registers handlers

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mcp", tags=["mcp"])

# One transport instance shared across requests.
# stateless_http=True is appropriate for horizontally-scaled deployments —
# no session state is held server-side between requests.
transport = StreamableHTTPServerTransport(
    mcp_session_id=None,   # clients supply their own session IDs
    stateless_http=True,
)


@router.post("")
async def mcp_endpoint(request: Request) -> Response:
    """Single Streamable HTTP endpoint for all MCP clients.

    Streaming clients (those that send Accept: text/event-stream) receive
    a streaming SSE response from within this same POST handler.
    Non-streaming clients receive a plain JSON response.
    Both use the same endpoint — no separate GET /sse endpoint needed.
    """
    async with transport.connect_http(request) as (read_stream, write_stream):
        await mcp.run(
            read_stream,
            write_stream,
            mcp.create_initialization_options(),
        )
    return Response(status_code=200)
```

---

## Step 6: Register the MCP Router in `src/main.py`

```python
from src.mcp.http_transport import router as mcp_router

app.include_router(mcp_router)
```

---

## Step 7: Configure MCP Clients

Because the server is HTTP-based, MCP clients connect by pointing at the endpoint URL directly — no `command`/`args` wrapper is needed.

**Claude Desktop** (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "rag-pipeline": {
      "type": "http",
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

**Quick curl test**:

```bash
# List all tools
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'

# Call a tool
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
      "name": "search_knowledge_base",
      "arguments": {
        "query": "how to configure authentication",
        "collection_name": "my-docs",
        "top_k": 3
      }
    }
  }'
```

---

## Done-When Checklist

| # | Criterion | Verify |
|---|-----------|--------|
| 1 | All Phase 7 Python packages import without errors | `python -c "import mcp; import structlog; import sentry_sdk"` |
| 2 | MCP server lists 7 tools | `POST /mcp` with `tools/list` → 7 tools returned |
| 3 | MCP `search_knowledge_base` returns Qdrant results | `POST /mcp` with `tools/call` and a valid collection + query |
| 4 | Streamable HTTP transport works at `POST /mcp` | curl test above returns JSON-RPC response |
| 5 | Claude Desktop can trigger ingestion via MCP | Configure `"type":"http","url":"http://localhost:8000/mcp"` and call `ingest_url` |

---

## Summary Report

Upon completion of this subtask, create a summary report at:
`rag-pipeline/ai-workspace/summary-reports/phase-7-subtask-1-mcp-server-tools-summary.md`

The summary report must include:
- **Subtask**: Phase 7, Subtask 1 — MCP Server Tools
- **Status**: Complete / Partial / Blocked
- **Date**: {ISO 8601 date}
- **Files Created/Modified**: List every file path
- **Key Decisions**: Any deviations from the plan and why
- **Issues Encountered**: Problems and resolutions
- **Dependencies for Next Subtask**: What the next subtask needs to know
- **Verification Results**: Output of Done-When checklist items