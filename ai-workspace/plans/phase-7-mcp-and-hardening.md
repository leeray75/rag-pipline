# Phase 7 — MCP Server, Observability, Polish & Production Hardening

> **Prerequisites**: Phase 6 complete — Chunks generated, FastEmbed embeddings working, Qdrant collections populated, JSON review UI functional, similarity search verified.
> **Ref**: [phase-0-index.md](phase-0-index.md) for pinned versions.

---

## Objective

Expose the full pipeline as MCP tools consumable by AI assistants via the **Streamable HTTP transport** (the current MCP standard), add distributed tracing with OpenTelemetry, set up Prometheus + Grafana dashboards, integrate LangSmith for agent evaluation, implement re-ingestion for updated docs, add JWT authentication, harden Docker Compose for production, and write comprehensive documentation.

---

## Key Version Pins (Phase 7 additions)

| Package | Version | Install |
|---|---|---|
| MCP Python SDK | 1.27.0 | `pip install mcp` |
| opentelemetry-api | 1.33.0 | `pip install opentelemetry-api` |
| opentelemetry-sdk | 1.33.0 | `pip install opentelemetry-sdk` |
| opentelemetry-instrumentation-fastapi | 0.54b0 | `pip install opentelemetry-instrumentation-fastapi` |
| opentelemetry-instrumentation-celery | 0.54b0 | `pip install opentelemetry-instrumentation-celery` |
| opentelemetry-instrumentation-httpx | 0.54b0 | `pip install opentelemetry-instrumentation-httpx` |
| opentelemetry-exporter-otlp | 1.33.0 | `pip install opentelemetry-exporter-otlp` |
| prometheus-fastapi-instrumentator | 7.1.0 | `pip install prometheus-fastapi-instrumentator` |
| python-jose | 3.4.0 | `pip install "python-jose[cryptography]"` |
| slowapi | 0.1.9 | `pip install slowapi` |
| structlog | 25.4.0 | `pip install structlog` |
| langsmith | 0.3.42 | `pip install langsmith` |
| sentry-sdk | 2.29.1 | `pip install "sentry-sdk[fastapi]"` |

### Infrastructure additions

| Component | Image | Purpose |
|---|---|---|
| Grafana | `grafana/grafana:11.6` | Dashboards |
| Grafana Tempo | `grafana/tempo:2.7` | Trace backend |
| Prometheus | `prom/prometheus:3.4` | Metrics scraping |
| Grafana Loki | `grafana/loki:3.5` | Log aggregation |

---

## Task 1: Add Phase 7 Python Dependencies

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

## Task 2: Build the MCP Server

**Working directory**: `rag-pipeline/apps/api/`

> **Transport note**: This plan uses the **Streamable HTTP transport** exclusively — the current MCP specification standard (introduced March 2025). The legacy SSE two-endpoint pattern (`GET /mcp/sse` + `POST /mcp/messages/`) and stdio are not implemented.

### 2.1 Create `src/mcp/__init__.py`

```python
"""MCP Server package — exposes pipeline tools to AI assistants via Streamable HTTP."""
```

### 2.2 Create `src/mcp/server.py`

```python
"""MCP Server — exposes RAG pipeline tools via the Model Context Protocol.

Transport: Streamable HTTP (current MCP spec standard).
Endpoint:  POST /mcp  (single unified endpoint for all clients)
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

### 2.3 Create `src/mcp/tool_handlers.py`

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

### 2.4 Create `src/mcp/http_transport.py`

This module mounts the MCP server into the FastAPI app using the **Streamable HTTP transport** — a single `POST /mcp` endpoint that handles all clients (streaming and non-streaming) without requiring a separate SSE event-stream endpoint.

```python
"""Streamable HTTP transport for embedding the MCP server into the FastAPI app.

The Streamable HTTP transport exposes a single endpoint:
    POST /mcp

Clients send JSON-RPC requests to this endpoint. The server responds either
as a standard JSON response (for non-streaming clients) or as a
server-sent event stream within the same HTTP response (for streaming clients),
negotiated via the Accept header. This replaces the legacy two-endpoint
SSE pattern (GET /sse + POST /messages/).

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
# stateless_http=True means no session state is held server-side between
# requests, which is appropriate for horizontally-scaled deployments.
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
    # The response is written directly to the transport; return empty 200
    # only if the transport did not already send a response.
    return Response(status_code=200)
```

### 2.5 Register the MCP router in `src/main.py`

```python
from src.mcp.http_transport import router as mcp_router

app.include_router(mcp_router)
```

### 2.6 Configure MCP clients to use Streamable HTTP

Because the server is HTTP-based, MCP clients connect by pointing at the endpoint URL. There is no `command`/`args` stdio wrapper.

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

**Any MCP HTTP client** (curl test):

```bash
# List tools
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

**Done when**:
- `POST /mcp` with `tools/list` returns all 7 tools
- `POST /mcp` with `tools/call` executes a tool and returns results
- Claude Desktop (or any MCP HTTP client) can trigger `ingest_url` via the endpoint

---

## Task 3: Configure Structured Logging

**Working directory**: `rag-pipeline/apps/api/`

### 3.1 Create `src/logging_config.py`

```python
"""Structured logging configuration using structlog.

Outputs JSON in production, pretty-printed in development.
"""

import logging
import os
import sys

import structlog


def configure_logging() -> None:
    """Configure structlog for the application.

    Set LOG_FORMAT=json for production (JSON lines).
    Set LOG_FORMAT=console for development (colored output).
    """
    log_format = os.getenv("LOG_FORMAT", "console")
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    # Shared processors
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if log_format == "json":
        # Production: JSON output for Loki / CloudWatch
        renderer = structlog.processors.JSONRenderer()
    else:
        # Development: colored console output
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging to use structlog formatter
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, log_level))
```

### 3.2 Initialize in `src/main.py`

Add at the top of the file, before `app` creation:

```python
from src.logging_config import configure_logging
configure_logging()
```

**Done when**: Application logs output as JSON when `LOG_FORMAT=json` is set.

---

## Task 4: Add OpenTelemetry Distributed Tracing

**Working directory**: `rag-pipeline/apps/api/`

### 4.1 Create `src/telemetry.py`

```python
"""OpenTelemetry configuration — traces exported to Grafana Tempo via OTLP."""

import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
    OTLPSpanExporter,
)
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def configure_telemetry(app=None) -> None:
    """Set up OpenTelemetry tracing.

    Instruments FastAPI, Celery, and httpx.
    Exports traces to OTLP endpoint (Grafana Tempo).
    """
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://tempo:4317")
    service_name = os.getenv("OTEL_SERVICE_NAME", "rag-pipeline-api")

    if os.getenv("OTEL_ENABLED", "true").lower() != "true":
        return

    # Resource identifies this service in traces
    resource = Resource.create(
        {
            "service.name": service_name,
            "service.version": "1.0.0",
            "deployment.environment": os.getenv("ENVIRONMENT", "development"),
        }
    )

    # Set up the tracer provider
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    # Instrument FastAPI
    if app:
        FastAPIInstrumentor.instrument_app(app)

    # Instrument Celery
    CeleryInstrumentor().instrument()

    # Instrument httpx (used by crawlers)
    HTTPXClientInstrumentor().instrument()
```

### 4.2 Initialize in `src/main.py` — after app creation

```python
from src.telemetry import configure_telemetry

# After: app = FastAPI(...)
configure_telemetry(app)
```

**Done when**: Traces appear in Grafana Tempo when the API is called.

---

## Task 5: Add Prometheus Metrics

**Working directory**: `rag-pipeline/apps/api/`

### 5.1 Create `src/metrics.py`

```python
"""Prometheus metrics — custom counters and histograms for pipeline monitoring."""

import os

from prometheus_client import Counter, Histogram, Info
from prometheus_fastapi_instrumentator import Instrumentator

# ---- Custom metrics ----

JOBS_CREATED = Counter(
    "rag_jobs_created_total",
    "Total ingestion jobs created",
    ["source_type"],
)

JOBS_COMPLETED = Counter(
    "rag_jobs_completed_total",
    "Total ingestion jobs completed successfully",
)

JOBS_FAILED = Counter(
    "rag_jobs_failed_total",
    "Total ingestion jobs that failed",
    ["failure_reason"],
)

AGENT_ROUNDS = Histogram(
    "rag_agent_rounds_per_job",
    "Number of audit-correction rounds per job",
    buckets=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
)

EMBED_LATENCY = Histogram(
    "rag_embed_latency_seconds",
    "Time to embed a batch of chunks",
    ["model_name"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
)

CHUNKS_EMBEDDED = Counter(
    "rag_chunks_embedded_total",
    "Total chunks embedded and upserted to Qdrant",
    ["collection_name"],
)

QDRANT_UPSERT_LATENCY = Histogram(
    "rag_qdrant_upsert_latency_seconds",
    "Time to upsert a batch to Qdrant",
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
)

BUILD_INFO = Info(
    "rag_pipeline_build",
    "Build information for the RAG pipeline",
)
BUILD_INFO.info(
    {
        "version": "1.0.0",
        "embedding_model": os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5"),
    }
)


def configure_metrics(app) -> Instrumentator:
    """Instrument FastAPI and expose /metrics endpoint.

    Returns the instrumentator for further customization.
    """
    instrumentator = Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        should_instrument_requests_inprogress=True,
        excluded_handlers=["/health", "/metrics", "/mcp"],
        inprogress_name="rag_http_requests_inprogress",
        inprogress_labels=True,
    )

    instrumentator.instrument(app)
    instrumentator.expose(app, endpoint="/metrics", include_in_schema=False)

    return instrumentator
```

### 5.2 Initialize in `src/main.py` — after app creation

```python
from src.metrics import configure_metrics

# After: app = FastAPI(...)
configure_metrics(app)
```

**Done when**: `GET /metrics` returns Prometheus-formatted metrics including custom `rag_*` counters.

---

## Task 6: Add LangSmith Integration

**Working directory**: `rag-pipeline/apps/api/`

### 6.1 Create `src/agents/langsmith_config.py`

```python
"""LangSmith configuration for agent run tracing.

LangSmith traces are enabled by setting environment variables:
  LANGSMITH_API_KEY=lsv2_pt_...
  LANGSMITH_PROJECT=rag-pipeline
  LANGCHAIN_TRACING_V2=true
"""

import os
import logging

logger = logging.getLogger(__name__)


def configure_langsmith() -> None:
    """Verify LangSmith environment variables are set.

    LangChain/LangGraph automatically trace runs when
    LANGCHAIN_TRACING_V2=true is set. This function
    validates the configuration and logs the status.
    """
    api_key = os.getenv("LANGSMITH_API_KEY")
    project = os.getenv("LANGSMITH_PROJECT", "rag-pipeline")
    tracing = os.getenv("LANGCHAIN_TRACING_V2", "false").lower()

    if tracing == "true" and api_key:
        # Ensure project is set
        os.environ.setdefault("LANGSMITH_PROJECT", project)
        logger.info(
            "LangSmith tracing enabled — project: %s", project
        )
    elif tracing == "true" and not api_key:
        logger.warning(
            "LANGCHAIN_TRACING_V2=true but LANGSMITH_API_KEY is not set. "
            "Tracing will not work."
        )
    else:
        logger.info("LangSmith tracing disabled")


def get_langsmith_run_url(run_id: str) -> str | None:
    """Generate a LangSmith UI link for a specific run."""
    api_key = os.getenv("LANGSMITH_API_KEY")
    project = os.getenv("LANGSMITH_PROJECT", "rag-pipeline")
    if not api_key:
        return None
    return f"https://smith.langchain.com/o/default/projects/p/{project}/r/{run_id}"
```

### 6.2 Initialize in `src/main.py`

```python
from src.agents.langsmith_config import configure_langsmith
configure_langsmith()
```

**Done when**: With `LANGCHAIN_TRACING_V2=true` and a valid API key, LangGraph agent runs appear in the LangSmith dashboard.

---

## Task 7: Configure Sentry Error Tracking

**Working directory**: `rag-pipeline/apps/api/`

### 7.1 Create `src/sentry_config.py`

```python
"""Sentry error tracking configuration."""

import os
import logging

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

logger = logging.getLogger(__name__)


def configure_sentry() -> None:
    """Initialize Sentry SDK if SENTRY_DSN is set."""
    dsn = os.getenv("SENTRY_DSN")
    if not dsn:
        logger.info("Sentry disabled — SENTRY_DSN not set")
        return

    environment = os.getenv("ENVIRONMENT", "development")
    release = os.getenv("RELEASE_VERSION", "1.0.0")

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        release=f"rag-pipeline@{release}",
        traces_sample_rate=0.1,  # 10% of transactions
        profiles_sample_rate=0.1,
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            CeleryIntegration(),
            SqlalchemyIntegration(),
        ],
        # Don't send PII
        send_default_pii=False,
    )
    logger.info("Sentry initialized — env=%s release=%s", environment, release)
```

### 7.2 Initialize in `src/main.py` — before app creation

```python
from src.sentry_config import configure_sentry
configure_sentry()
```

**Done when**: Unhandled exceptions appear in the Sentry dashboard.

---

## Task 8: Add JWT Authentication

**Working directory**: `rag-pipeline/apps/api/`

### 8.1 Create `src/auth/__init__.py`

```python
"""Authentication package — JWT-based auth for the dashboard and API."""
```

### 8.2 Create `src/auth/jwt.py`

```python
"""JWT authentication utilities."""

import os
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

# Configuration
JWT_SECRET = os.getenv("JWT_SECRET", "CHANGE-ME-IN-PRODUCTION")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "24"))

security = HTTPBearer()


class TokenPayload(BaseModel):
    """Decoded JWT payload."""

    sub: str  # user ID or email
    exp: datetime
    iat: datetime
    role: str = "viewer"  # viewer | editor | admin


class TokenResponse(BaseModel):
    """Response from the login endpoint."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int


def create_access_token(
    subject: str,
    role: str = "viewer",
    expires_delta: timedelta | None = None,
) -> str:
    """Create a JWT access token."""
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(hours=JWT_EXPIRY_HOURS))

    payload = {
        "sub": subject,
        "role": role,
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> TokenPayload:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return TokenPayload(**payload)
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> TokenPayload:
    """FastAPI dependency — extracts and validates the JWT from the Authorization header."""
    return decode_token(credentials.credentials)


async def require_admin(
    user: TokenPayload = Depends(get_current_user),
) -> TokenPayload:
    """FastAPI dependency — requires admin role."""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return user


async def require_editor(
    user: TokenPayload = Depends(get_current_user),
) -> TokenPayload:
    """FastAPI dependency — requires editor or admin role."""
    if user.role not in ("editor", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Editor or admin role required",
        )
    return user
```

### 8.3 Create `src/routers/auth.py`

```python
"""Auth API — login and token management."""

import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.auth.jwt import TokenResponse, create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])

# Simple user store — replace with database in production
USERS: dict[str, dict] = {
    os.getenv("ADMIN_EMAIL", "admin@example.com"): {
        "password": os.getenv("ADMIN_PASSWORD", "changeme"),
        "role": "admin",
    },
}


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """Authenticate and return a JWT access token."""
    user = USERS.get(request.email)
    if not user or user["password"] != request.password:
        raise HTTPException(401, "Invalid credentials")

    token = create_access_token(
        subject=request.email,
        role=user["role"],
    )
    return TokenResponse(
        access_token=token,
        expires_in=24 * 3600,
    )
```

### 8.4 Register auth router and protect sensitive routes

In `src/main.py`:

```python
from src.routers.auth import router as auth_router

app.include_router(auth_router, prefix="/api/v1")
```

To protect a route, add the dependency:

```python
from src.auth.jwt import get_current_user, require_admin

@router.post("/jobs/{job_id}/embed", dependencies=[Depends(require_editor)])
async def start_embedding(...):
    ...
```

**Done when**: `POST /api/v1/auth/login` returns a JWT, and protected routes reject unauthenticated requests with 401.

---

## Task 9: Add Rate Limiting

**Working directory**: `rag-pipeline/apps/api/`

### 9.1 Create `src/rate_limit.py`

```python
"""Rate limiting configuration using slowapi."""

import os

from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.requests import Request
from starlette.responses import JSONResponse

# Default: 100 requests per minute per IP
DEFAULT_LIMIT = os.getenv("RATE_LIMIT", "100/minute")

limiter = Limiter(key_func=get_remote_address, default_limits=[DEFAULT_LIMIT])


async def rate_limit_exceeded_handler(
    request: Request, exc: RateLimitExceeded
) -> JSONResponse:
    """Custom handler for rate limit exceeded errors."""
    return JSONResponse(
        status_code=429,
        content={
            "error": "Rate limit exceeded",
            "detail": str(exc.detail),
            "retry_after": exc.retry_after,
        },
    )
```

### 9.2 Initialize in `src/main.py`

```python
from slowapi.errors import RateLimitExceeded
from src.rate_limit import limiter, rate_limit_exceeded_handler

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
```

**Done when**: Exceeding 100 requests/minute returns a 429 response.

---

## Task 10: Implement Re-Ingestion (Delta Updates)

**Working directory**: `rag-pipeline/apps/api/`

### 10.1 Create `src/ingest/reingestion.py`

```python
"""Re-ingestion service — detect updated docs and trigger delta pipeline.

Compares fetched content hashes to detect changes since last ingestion.
Only re-processes documents whose content has actually changed.
"""

import hashlib
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.document import Document
from src.models.chunk import ChunkRecord

logger = logging.getLogger(__name__)


class ReingestionService:
    """Detects changes in source documentation and triggers re-processing."""

    @staticmethod
    def content_hash(content: str) -> str:
        """SHA-256 hash of document content."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    async def detect_changes(
        self,
        *,
        job_id: str,
        new_documents: list[dict],
        db: AsyncSession,
    ) -> dict:
        """Compare new document content against stored hashes.

        Parameters
        ----------
        job_id : str
            The original job ID to compare against.
        new_documents : list[dict]
            Each dict: {source_url, content, title}.
        db : AsyncSession
            Database session.

        Returns
        -------
        dict with keys: added, updated, unchanged, removed
        """
        # Load existing documents for this job
        stmt = select(Document).where(Document.job_id == job_id)
        result = await db.execute(stmt)
        existing = {d.source_url: d for d in result.scalars().all()}

        new_urls = {d["source_url"] for d in new_documents}
        existing_urls = set(existing.keys())

        added = []
        updated = []
        unchanged = []
        removed = list(existing_urls - new_urls)

        for doc_data in new_documents:
            url = doc_data["source_url"]
            new_hash = self.content_hash(doc_data["content"])

            if url not in existing:
                added.append(url)
            elif existing[url].content_hash != new_hash:
                updated.append(url)
            else:
                unchanged.append(url)

        logger.info(
            "Re-ingestion delta: added=%d updated=%d unchanged=%d removed=%d",
            len(added),
            len(updated),
            len(unchanged),
            len(removed),
        )

        return {
            "added": added,
            "updated": updated,
            "unchanged": unchanged,
            "removed": removed,
        }

    async def invalidate_chunks(
        self,
        *,
        document_ids: list[str],
        db: AsyncSession,
    ) -> int:
        """Delete chunks for documents that need re-processing.

        Returns the number of chunks deleted.
        """
        from sqlalchemy import delete

        stmt = delete(ChunkRecord).where(
            ChunkRecord.document_id.in_(document_ids)
        )
        result = await db.execute(stmt)
        await db.commit()
        deleted = result.rowcount
        logger.info("Invalidated %d chunks for %d documents", deleted, len(document_ids))
        return deleted
```

### 10.2 Add `content_hash` column to Document model

In `src/models/document.py`, add to the `Document` class:

```python
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
```

### 10.3 Generate migration

```bash
cd rag-pipeline/apps/api
alembic revision --autogenerate -m "add content_hash to documents"
alembic upgrade head
```

**Done when**: `ReingestionService().detect_changes(...)` correctly identifies added, updated, unchanged, and removed documents.

---

## Task 11: Add SSRF Prevention

**Working directory**: `rag-pipeline/apps/api/`

### 11.1 Create `src/security/url_validator.py`

```python
"""URL validation — prevents SSRF attacks by blocking private IP ranges."""

import ipaddress
import logging
import socket
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# RFC 1918 and other private ranges
BLOCKED_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),  # link-local
    ipaddress.ip_network("::1/128"),          # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),         # IPv6 private
    ipaddress.ip_network("fe80::/10"),        # IPv6 link-local
]


class SSRFError(Exception):
    """Raised when a URL resolves to a blocked IP address."""


def validate_url(url: str) -> str:
    """Validate a URL is safe to fetch.

    Checks:
    1. Scheme is http or https.
    2. Hostname is not empty.
    3. Resolved IP is not in a private/internal range.

    Returns the validated URL.
    Raises SSRFError if the URL is unsafe.
    """
    parsed = urlparse(url)

    # Check scheme
    if parsed.scheme not in ("http", "https"):
        raise SSRFError(f"Unsupported scheme: {parsed.scheme}")

    # Check hostname
    hostname = parsed.hostname
    if not hostname:
        raise SSRFError("Missing hostname")

    # Resolve hostname to IP
    try:
        addr_info = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        raise SSRFError(f"Cannot resolve hostname: {hostname}")

    for _, _, _, _, sockaddr in addr_info:
        ip = ipaddress.ip_address(sockaddr[0])
        for network in BLOCKED_NETWORKS:
            if ip in network:
                raise SSRFError(
                    f"URL resolves to blocked IP range: {ip} ({network})"
                )

    logger.debug("URL validated: %s", url)
    return url
```

**Done when**: `validate_url("http://192.168.1.1/secret")` raises `SSRFError`.

---

## Task 12: Harden Docker Compose for Production

**Working directory**: `rag-pipeline/infra/`

### 12.1 Create `docker-compose.prod.yml`

```yaml
# Production overrides — use with:
# docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

services:
  api:
    restart: always
    deploy:
      resources:
        limits:
          cpus: "2.0"
          memory: 2G
        reservations:
          cpus: "0.5"
          memory: 512M
    environment:
      - ENVIRONMENT=production
      - LOG_FORMAT=json
      - OTEL_ENABLED=true
      - OTEL_EXPORTER_OTLP_ENDPOINT=http://tempo:4317
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  web:
    restart: always
    deploy:
      resources:
        limits:
          cpus: "1.0"
          memory: 1G
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000"]
      interval: 30s
      timeout: 10s
      retries: 3

  celery-worker:
    restart: always
    deploy:
      resources:
        limits:
          cpus: "2.0"
          memory: 3G
        reservations:
          cpus: "0.5"
          memory: 1G
    environment:
      - CELERY_CONCURRENCY=8
      - ENVIRONMENT=production
      - LOG_FORMAT=json
    healthcheck:
      test: ["CMD", "celery", "-A", "src.workers", "inspect", "ping"]
      interval: 60s
      timeout: 10s
      retries: 3

  postgres:
    restart: always
    deploy:
      resources:
        limits:
          cpus: "1.0"
          memory: 1G
    command: >
      postgres
      -c max_connections=100
      -c shared_buffers=256MB
      -c effective_cache_size=768MB
      -c work_mem=4MB
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    restart: always
    deploy:
      resources:
        limits:
          cpus: "0.5"
          memory: 256M
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  qdrant:
    restart: always
    deploy:
      resources:
        limits:
          cpus: "2.0"
          memory: 4G
        reservations:
          cpus: "0.5"
          memory: 1G
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/readyz"]
      interval: 30s
      timeout: 10s
      retries: 3

  # ---- Observability stack ----

  tempo:
    image: grafana/tempo:2.7
    restart: always
    command: ["-config.file=/etc/tempo.yaml"]
    volumes:
      - ./tempo/tempo.yaml:/etc/tempo.yaml:ro
      - tempo_data:/var/tempo
    ports:
      - "4317:4317"   # OTLP gRPC
      - "4318:4318"   # OTLP HTTP
    deploy:
      resources:
        limits:
          cpus: "0.5"
          memory: 512M

  prometheus:
    image: prom/prometheus:3.4
    restart: always
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus_data:/prometheus
    ports:
      - "9090:9090"
    deploy:
      resources:
        limits:
          cpus: "0.5"
          memory: 512M

  loki:
    image: grafana/loki:3.5
    restart: always
    command: ["-config.file=/etc/loki/local-config.yaml"]
    volumes:
      - loki_data:/loki
    ports:
      - "3100:3100"
    deploy:
      resources:
        limits:
          cpus: "0.5"
          memory: 512M

  grafana:
    image: grafana/grafana:11.6
    restart: always
    volumes:
      - grafana_data:/var/lib/grafana
      - ./grafana/provisioning:/etc/grafana/provisioning:ro
      - ./grafana/dashboards:/var/lib/grafana/dashboards:ro
    ports:
      - "3001:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD:-admin}
      - GF_SECURITY_ADMIN_USER=admin
    deploy:
      resources:
        limits:
          cpus: "0.5"
          memory: 512M

volumes:
  tempo_data:
  prometheus_data:
  loki_data:
  grafana_data:
```

**Done when**: `docker compose -f docker-compose.yml -f docker-compose.prod.yml config` validates without errors.

---

## Task 13: Create Observability Configuration Files

**Working directory**: `rag-pipeline/infra/`

### 13.1 Create `prometheus/prometheus.yml`

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: "rag-pipeline-api"
    static_configs:
      - targets: ["api:8000"]
    metrics_path: /metrics
    scrape_interval: 10s

  - job_name: "qdrant"
    static_configs:
      - targets: ["qdrant:6333"]
    metrics_path: /metrics
    scrape_interval: 30s
```

### 13.2 Create `tempo/tempo.yaml`

```yaml
server:
  http_listen_port: 3200

distributor:
  receivers:
    otlp:
      protocols:
        grpc:
          endpoint: "0.0.0.0:4317"
        http:
          endpoint: "0.0.0.0:4318"

storage:
  trace:
    backend: local
    local:
      path: /var/tempo/traces
    wal:
      path: /var/tempo/wal
```

### 13.3 Create `grafana/provisioning/datasources/datasources.yml`

```yaml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true

  - name: Tempo
    type: tempo
    access: proxy
    url: http://tempo:3200

  - name: Loki
    type: loki
    access: proxy
    url: http://loki:3100
```

### 13.4 Create `grafana/dashboards/pipeline-throughput.json`

```json
{
  "dashboard": {
    "title": "RAG Pipeline — Throughput",
    "uid": "rag-throughput",
    "panels": [
      {
        "title": "Jobs Created (rate)",
        "type": "timeseries",
        "targets": [
          {
            "expr": "rate(rag_jobs_created_total[5m])",
            "legendFormat": "{{source_type}}"
          }
        ],
        "gridPos": { "h": 8, "w": 12, "x": 0, "y": 0 }
      },
      {
        "title": "Agent Rounds Distribution",
        "type": "histogram",
        "targets": [
          {
            "expr": "rag_agent_rounds_per_job_bucket",
            "legendFormat": "{{le}} rounds"
          }
        ],
        "gridPos": { "h": 8, "w": 12, "x": 12, "y": 0 }
      },
      {
        "title": "Embed Latency P95",
        "type": "stat",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(rag_embed_latency_seconds_bucket[5m]))",
            "legendFormat": "p95"
          }
        ],
        "gridPos": { "h": 4, "w": 6, "x": 0, "y": 8 }
      },
      {
        "title": "Chunks Embedded Total",
        "type": "stat",
        "targets": [
          {
            "expr": "rag_chunks_embedded_total",
            "legendFormat": "{{collection_name}}"
          }
        ],
        "gridPos": { "h": 4, "w": 6, "x": 6, "y": 8 }
      },
      {
        "title": "Qdrant Upsert Latency",
        "type": "timeseries",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(rag_qdrant_upsert_latency_seconds_bucket[5m]))",
            "legendFormat": "p95"
          }
        ],
        "gridPos": { "h": 8, "w": 12, "x": 12, "y": 8 }
      }
    ]
  }
}
```

**Done when**: Grafana starts with pre-provisioned Prometheus, Tempo, and Loki data sources, plus the throughput dashboard.

---

## Task 14: Add Health Check Endpoint

**Working directory**: `rag-pipeline/apps/api/`

### 14.1 Create `src/routers/health.py`

```python
"""Health check endpoints for Docker and load balancer probing."""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    """Basic liveness check — always returns 200 if the process is running."""
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness(db: AsyncSession = Depends(get_db)):
    """Readiness check — verifies Postgres, Redis, and Qdrant connectivity.

    Returns 200 only if all dependencies are reachable.
    """
    checks = {}

    # Postgres
    try:
        await db.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception as e:
        checks["postgres"] = f"error: {e}"

    # Redis
    try:
        from src.workers.celery_app import celery_app

        celery_app.control.ping(timeout=2)
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {e}"

    # Qdrant
    try:
        from qdrant_client import QdrantClient
        import os

        client = QdrantClient(url=os.getenv("QDRANT_URL", "http://localhost:6333"))
        client.get_collections()
        checks["qdrant"] = "ok"
    except Exception as e:
        checks["qdrant"] = f"error: {e}"

    all_ok = all(v == "ok" for v in checks.values())
    status_code = 200 if all_ok else 503

    from starlette.responses import JSONResponse

    return JSONResponse(
        status_code=status_code,
        content={"status": "ready" if all_ok else "degraded", "checks": checks},
    )
```

### 14.2 Register in `src/main.py`

```python
from src.routers.health import router as health_router

app.include_router(health_router)
```

**Done when**: `GET /health` → 200, `GET /health/ready` → 200 when all services are up, 503 when any is down.

---

## Task 15: Add Sentry to the Next.js Frontend

**Working directory**: `rag-pipeline/apps/web/`

### 15.1 Install Sentry SDK

```bash
pnpm add @sentry/nextjs
```

### 15.2 Initialize Sentry

```bash
npx @sentry/wizard@latest -i nextjs
```

Follow the wizard prompts. This creates:
- `sentry.client.config.ts`
- `sentry.server.config.ts`
- `sentry.edge.config.ts`
- Updates `next.config.ts` with `withSentryConfig()`

### 15.3 Update `sentry.client.config.ts`

```typescript
import * as Sentry from "@sentry/nextjs";

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  environment: process.env.NODE_ENV,
  tracesSampleRate: 0.1,
  replaysSessionSampleRate: 0.1,
  replaysOnErrorSampleRate: 1.0,
});
```

**Done when**: Frontend errors appear in Sentry dashboard.

---

## Task 16: Write Documentation

**Working directory**: `rag-pipeline/`

### 16.1 Create `README.md`

````markdown
# RAG Pipeline — AI Knowledge Base Ingestion System

A production-grade pipeline that crawls documentation websites, converts HTML
to structured Markdown, validates quality via AI agents, and ingests into
a Qdrant vector database for RAG retrieval.

## Quick Start

```bash
# Clone and install
git clone <repo-url>
cd rag-pipeline
pnpm install
cd apps/api && pip install -e ".[dev]"

# Start infrastructure
cd infra && docker compose up -d

# Run migrations
cd apps/api && alembic upgrade head

# Start development servers
pnpm dev  # starts both API and web
```

## Architecture

```
URL → Fetch → Convert → Audit Agent → Correction Agent → Human Review → Chunk → Embed → Qdrant
```

## API Documentation

FastAPI auto-generates OpenAPI docs:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## MCP Integration

The pipeline exposes its tools via the MCP **Streamable HTTP transport**
(MCP spec 2025-03-26). A single endpoint handles all clients:

    POST http://localhost:8000/mcp

Configure in Claude Desktop (`claude_desktop_config.json`):

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

Available tools: `ingest_url`, `get_job_status`, `list_documents`,
`get_audit_report`, `search_knowledge_base`, `approve_job`,
`get_collection_stats`.

Quick test (no client needed):

```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

## Observability

- **Grafana**: http://localhost:3001 (admin/admin)
- **Prometheus**: http://localhost:9090
- **Traces**: Grafana → Explore → Tempo

## Environment Variables

See `apps/api/.env.example` for all configuration options.
````

### 16.2 Create `docs/runbook.md`

````markdown
# Operations Runbook

## Startup

```bash
# Development
cd infra && docker compose up -d
cd apps/api && uvicorn src.main:app --reload
cd apps/web && pnpm dev

# Production
cd infra && docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## Common Issues

### Celery worker not processing tasks
1. Check Redis connectivity: `redis-cli ping`
2. Check worker logs: `docker compose logs celery-worker`
3. Restart: `docker compose restart celery-worker`

### Qdrant collection not queryable
1. Check collection exists: `curl http://localhost:6333/collections`
2. Verify vector count: `curl http://localhost:6333/collections/{name}`
3. Check embedding dimensions match (should be 384)

### Agent loop stuck (non-convergence)
1. Check max_rounds guard (default: 5)
2. Review LangSmith traces for the job
3. Manual override: `POST /api/v1/jobs/{id}/force-complete`

### FastEmbed model not loading
1. Check cache dir: `~/.cache/fastembed/` or `$FASTEMBED_CACHE_DIR`
2. Delete cache and re-download: `rm -rf ~/.cache/fastembed/`
3. Verify: `python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5')"`

### Database migration failed
1. Check current head: `alembic current`
2. View history: `alembic history`
3. Downgrade if needed: `alembic downgrade -1`
4. Fix migration and re-run: `alembic upgrade head`

### MCP endpoint not responding
1. Confirm the API is running: `curl http://localhost:8000/health`
2. Test the endpoint directly:
   ```bash
   curl -X POST http://localhost:8000/mcp \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
   ```
3. Check API logs for import errors in `src/mcp/`

## Manual Override Procedures

### Skip audit for a document
```sql
UPDATE documents SET status = 'approved' WHERE id = '<doc-id>';
```

### Force re-embedding
```sql
UPDATE chunks SET embedding_status = 'pending' WHERE job_id = '<job-id>';
```
Then trigger: `POST /api/v1/ingest/jobs/{id}/embed`

### Delete a Qdrant collection
```bash
curl -X DELETE http://localhost:6333/collections/{name}
```

## Backup & Recovery

### Qdrant snapshots
```bash
curl -X POST http://localhost:6333/collections/{name}/snapshots
```

### Postgres backup
```bash
docker compose exec postgres pg_dump -U postgres rag_pipeline > backup.sql
```
````

**Done when**: README.md and runbook.md are complete with accurate instructions.

---

## Task 17: Update Environment Variables

### 17.1 Final `apps/api/.env.example`

Append Phase 7 variables:

```env
# --- Phase 7: MCP, Observability, Auth ---

# JWT
JWT_SECRET=CHANGE-ME-IN-PRODUCTION
JWT_EXPIRY_HOURS=24
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=changeme

# OpenTelemetry
OTEL_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=http://tempo:4317
OTEL_SERVICE_NAME=rag-pipeline-api

# LangSmith
LANGCHAIN_TRACING_V2=false
LANGSMITH_API_KEY=
LANGSMITH_PROJECT=rag-pipeline

# Sentry
SENTRY_DSN=

# Logging
LOG_FORMAT=console
LOG_LEVEL=INFO

# Rate Limiting
RATE_LIMIT=100/minute

# Grafana
GRAFANA_ADMIN_PASSWORD=admin

# Environment
ENVIRONMENT=development
RELEASE_VERSION=1.0.0
```

**Done when**: `.env.example` contains all configuration for all 7 phases.

---

## Task 18: Write Integration Tests

**Working directory**: `rag-pipeline/apps/api/`

### 18.1 Create `tests/test_mcp_server.py`

```python
"""Tests for the MCP server tool registration."""

import pytest

from src.mcp.server import mcp


@pytest.mark.asyncio
async def test_list_tools_returns_all_tools():
    """All 7 MCP tools are registered."""
    # Invoke the registered list_tools handler via the public MCP request API
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

> **Note**: The tests use `mcp.handle_request()` (the public MCP SDK API) rather than the internal `mcp._tool_handlers` dict, which is an implementation detail subject to change across SDK versions.

### 18.2 Create `tests/test_mcp_http_transport.py`

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
    assert response.status_code in (200, 400)
    body = response.json()
    # JSON-RPC errors are returned in the error field, not as HTTP errors
    assert "error" in body or response.status_code == 400
```

### 18.3 Create `tests/test_auth.py`

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

### 18.4 Create `tests/test_url_validator.py`

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

### 18.5 Run all tests

```bash
cd rag-pipeline/apps/api && python -m pytest tests/ -v
```

**Done when**: All tests pass.

---

## Done-When Checklist

| # | Criterion | Verify |
|---|-----------|--------|
| 1 | MCP server lists 7 tools | `POST /mcp` with `tools/list` → 7 tools returned |
| 2 | MCP `search_knowledge_base` returns Qdrant results | `POST /mcp` with `tools/call` → valid results |
| 3 | Streamable HTTP transport works at `POST /mcp` | `curl -X POST localhost:8000/mcp -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'` |
| 4 | Claude Desktop can trigger ingestion via MCP | Configure `"type":"http","url":"http://localhost:8000/mcp"` and call `ingest_url` |
| 5 | Structured logging outputs JSON in production | `LOG_FORMAT=json python -m uvicorn src.main:app` → JSON output |
| 6 | OpenTelemetry traces appear in Grafana Tempo | Submit a job → view trace in Grafana Explore → Tempo |
| 7 | Prometheus metrics at `/metrics` include `rag_*` counters | `curl localhost:8000/metrics \| grep rag_` |
| 8 | Grafana dashboard shows pipeline throughput | Open http://localhost:3001 → Pipeline Throughput dashboard |
| 9 | LangSmith traces show agent runs | Set `LANGCHAIN_TRACING_V2=true` → run audit agent → check smith.langchain.com |
| 10 | JWT auth protects sensitive endpoints | `curl -X POST /api/v1/ingest/jobs/{id}/embed` without token → 401 |
| 11 | Rate limiting returns 429 when exceeded | Send >100 requests/min → 429 response |
| 12 | SSRF prevention blocks private IPs | Submit `http://192.168.1.1` → rejected |
| 13 | Re-ingestion detects changed documents | Re-fetch same URL with modified content → delta detected |
| 14 | Health check endpoints work | `GET /health` → 200, `GET /health/ready` → 200 or 503 |
| 15 | Sentry captures frontend + backend errors | Throw test error → appears in Sentry |
| 16 | Docker Compose prod overlay validates | `docker compose -f ... config` succeeds |
| 17 | README.md covers setup, architecture, MCP, observability | File exists with complete sections |
| 18 | Runbook covers startup, common issues, manual overrides | File exists with all scenarios |
| 19 | All Phase 7 tests pass | `pytest tests/ -v -k "mcp or auth or url_validator"` |
| 20 | Load test: 5 concurrent jobs with 50 docs each complete | Run load test script and verify all jobs reach "ingested" |