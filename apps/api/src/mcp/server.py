"""MCP Server — exposes RAG pipeline tools via the Model Context Protocol.

Transport: Streamable HTTP (current MCP spec standard, March 2025).
Endpoint:  POST /mcp  (single unified endpoint for all clients)

Uses FastMCP high-level framework which handles:
- Streamable HTTP transport (session management, SSE/JSON negotiation)
- Tool registration and schema generation
- Error handling

Do NOT import mcp.server.sse or mcp.server.stdio — those transports are
not used in this implementation.
"""

import json
import logging

from mcp.server import FastMCP

logger = logging.getLogger(__name__)

# Create the MCP server instance using FastMCP.
# streamable_http_path="/mcp" is the default but set explicitly for clarity.
# stateless_http=True is appropriate for horizontally-scaled deployments —
# no session state is held server-side between requests.
mcp = FastMCP(
    "rag-pipeline",
    stateless_http=True,
    streamable_http_path="/mcp",
)


# ---------------------------------------------------------------------------
# Tool: ingest_url
# ---------------------------------------------------------------------------


@mcp.tool(
    name="ingest_url",
    description=(
        "Create an ingestion job from a URL. "
        "Optionally crawl all linked pages."
    ),
)
async def ingest_url(url: str, crawl_all: bool = False) -> str:
    """Create an ingestion job from a URL."""
    from src.workers.crawl_tasks import crawl_url_task

    task = crawl_url_task.delay(url, crawl_all=crawl_all)
    result = {
        "job_id": task.id,
        "url": url,
        "crawl_all": crawl_all,
        "status": "job_created",
        "message": f"Ingestion job created for {url}",
    }
    return json.dumps(result, indent=2)


# ---------------------------------------------------------------------------
# Tool: get_job_status
# ---------------------------------------------------------------------------


@mcp.tool(
    name="get_job_status",
    description="Get the current status, progress, and round count for a job.",
)
async def get_job_status(job_id: str) -> str:
    """Get job status from Postgres."""
    from sqlalchemy import select

    from src.database import get_async_session
    from src.models.job import Job

    async with get_async_session() as db:
        stmt = select(Job).where(Job.id == job_id)
        result = await db.execute(stmt)
        job = result.scalar_one_or_none()
        if not job:
            return json.dumps({"error": f"Job {job_id} not found"})
        return json.dumps(
            {
                "job_id": str(job.id),
                "status": job.status,
                "progress": job.progress,
                "audit_rounds": job.audit_rounds,
                "created_at": str(job.created_at),
                "updated_at": str(job.updated_at),
            },
            indent=2,
        )


# ---------------------------------------------------------------------------
# Tool: list_documents
# ---------------------------------------------------------------------------


@mcp.tool(
    name="list_documents",
    description="List all documents for a job with their current status.",
)
async def list_documents(job_id: str) -> str:
    """List all documents for a job."""
    from sqlalchemy import select

    from src.database import get_async_session
    from src.models.document import Document

    async with get_async_session() as db:
        stmt = (
            select(Document)
            .where(Document.job_id == job_id)
            .order_by(Document.created_at)
        )
        result = await db.execute(stmt)
        docs = result.scalars().all()
        return json.dumps(
            {
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
            },
            indent=2,
        )


# ---------------------------------------------------------------------------
# Tool: get_audit_report
# ---------------------------------------------------------------------------


@mcp.tool(
    name="get_audit_report",
    description="Get the structured audit report JSON for a specific round.",
)
async def get_audit_report(job_id: str, round: int = 1) -> str:
    """Get audit report for a specific round."""
    from sqlalchemy import select

    from src.database import get_async_session
    from src.models.audit import AuditReport

    async with get_async_session() as db:
        stmt = (
            select(AuditReport)
            .where(AuditReport.job_id == job_id)
            .where(AuditReport.round_number == round)
        )
        result = await db.execute(stmt)
        report = result.scalar_one_or_none()
        if not report:
            return json.dumps(
                {"error": f"No audit report for job {job_id} round {round}"}
            )
        return json.dumps(
            {
                "job_id": job_id,
                "round": round,
                "report": report.report_json,
            },
            indent=2,
            default=str,
        )


# ---------------------------------------------------------------------------
# Tool: search_knowledge_base
# ---------------------------------------------------------------------------


@mcp.tool(
    name="search_knowledge_base",
    description=(
        "Query the Qdrant vector store and return "
        "ranked chunks with relevance scores."
    ),
)
async def search_knowledge_base(
    query: str,
    collection_name: str,
    top_k: int = 5,
) -> str:
    """Search Qdrant collection using FastEmbed."""
    from src.ingest.qdrant_ingest import QdrantIngestService

    service = QdrantIngestService()
    results = service.test_similarity_search(
        collection_name=collection_name,
        query_text=query,
        limit=top_k,
    )
    return json.dumps(
        {
            "query": query,
            "collection": collection_name,
            "top_k": top_k,
            "results": results,
        },
        indent=2,
        default=str,
    )


# ---------------------------------------------------------------------------
# Tool: approve_job
# ---------------------------------------------------------------------------


@mcp.tool(
    name="approve_job",
    description=(
        "Trigger human approval for a job. "
        "Starts JSON generation and embedding pipeline."
    ),
)
async def approve_job(job_id: str) -> str:
    """Approve a job and trigger JSON generation pipeline."""
    from src.workers.ingest_tasks import chunk_job_task

    task = chunk_job_task.delay(job_id)
    return json.dumps(
        {
            "job_id": job_id,
            "task_id": task.id,
            "status": "approved",
            "message": "Job approved — chunking pipeline started",
        },
        indent=2,
    )


# ---------------------------------------------------------------------------
# Tool: get_collection_stats
# ---------------------------------------------------------------------------


@mcp.tool(
    name="get_collection_stats",
    description="Get Qdrant collection metadata and statistics.",
)
async def get_collection_stats(collection_name: str) -> str:
    """Get Qdrant collection statistics."""
    from src.ingest.qdrant_ingest import QdrantIngestService

    service = QdrantIngestService()
    stats = service.get_collection_stats(collection_name)
    return json.dumps(stats, indent=2, default=str)
