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
        # NOTE: /mcp (not /mcp/sse) — the MCP endpoint is Streamable HTTP at POST /mcp
        excluded_handlers=["/health", "/metrics", "/mcp"],
        inprogress_name="rag_http_requests_inprogress",
        inprogress_labels=True,
    )

    instrumentator.instrument(app)
    instrumentator.expose(app, endpoint="/metrics", include_in_schema=False)

    return instrumentator
