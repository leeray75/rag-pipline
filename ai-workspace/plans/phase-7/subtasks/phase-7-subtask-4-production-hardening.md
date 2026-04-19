# Phase 7, Subtask 4 — Production Hardening

> **Phase**: Phase 7 — MCP Server, Observability & Production Hardening
> **Prerequisites**: Phase 6 complete; Phase 7 Subtasks 1-3 complete (dependencies installed, MCP server working via Streamable HTTP at `POST /mcp`, observability configured, auth & security in place)
> **Scope**: Re-ingestion delta updates, docker-compose.prod.yml with observability services, health check endpoints, documentation (README + runbook), environment variable updates

> **Note**: This subtask uses only open-source, self-hosted, free tools. No paid SaaS services (LangSmith, Sentry, Datadog, etc.) are used. Agent run observability is handled by OpenTelemetry → Grafana Tempo. Error tracking is handled by structlog JSON logs → Grafana Loki + Prometheus error counters.

---

## Relevant Technology Stack

| Package / Component | Version | Notes |
|---|---|---|
| Docker Compose | 2.x | Compose V2 |
| Grafana | 11.6 | Docker image `grafana/grafana:11.6` |
| Grafana Tempo | 2.7 | Docker image `grafana/tempo:2.7` |
| Prometheus | 3.4 | Docker image `prom/prometheus:3.4` |
| Grafana Loki | 3.5 | Docker image `grafana/loki:3.5` |
| SQLAlchemy | 2.0.49 | Already installed |
| Alembic | 1.18.4 | Already installed |
| FastAPI | 0.135.3 | Already installed |

---

## Files to Create/Modify

| Action | File Path |
|---|---|
| Create | `rag-pipeline/apps/api/src/ingest/reingestion.py` |
| Modify | `rag-pipeline/apps/api/src/models/document.py` (add content_hash column) |
| Create | `rag-pipeline/infra/docker-compose.prod.yml` |
| Create | `rag-pipeline/apps/api/src/routers/health.py` |
| Create | `rag-pipeline/README.md` |
| Create | `rag-pipeline/docs/runbook.md` |
| Modify | `rag-pipeline/apps/api/.env.example` (append Phase 7 variables) |
| Modify | `rag-pipeline/apps/api/src/main.py` (register health router) |

---

## Step 1: Implement Re-Ingestion (Delta Updates)

**Working directory**: `rag-pipeline/apps/api/`

### 1.1 Create `src/ingest/reingestion.py`

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

### 1.2 Add `content_hash` column to Document model

In `src/models/document.py`, add to the `Document` class:

```python
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
```

### 1.3 Generate migration

```bash
cd rag-pipeline/apps/api
alembic revision --autogenerate -m "add content_hash to documents"
alembic upgrade head
```

---

## Step 2: Harden Docker Compose for Production

**Working directory**: `rag-pipeline/infra/`

### 2.1 Create `docker-compose.prod.yml`

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

---

## Step 3: Add Health Check Endpoints

**Working directory**: `rag-pipeline/apps/api/`

### 3.1 Create `src/routers/health.py`

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

### 3.2 Register in `src/main.py`

```python
from src.routers.health import router as health_router

app.include_router(health_router)
```

---

## Step 4: Write Documentation

**Working directory**: `rag-pipeline/`

### 4.1 Create `README.md`

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

Quick test (no client required):

```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

## Observability (all open-source, self-hosted)

- **Grafana**: http://localhost:3001 (admin/admin)
- **Prometheus metrics**: http://localhost:9090
- **Distributed traces**: Grafana → Explore → Tempo
- **Logs**: Grafana → Explore → Loki
- **Agent run traces**: OpenTelemetry spans visible in Grafana Tempo

## Environment Variables

See `apps/api/.env.example` for all configuration options.
````

### 4.2 Create `docs/runbook.md`

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
2. Review agent traces in Grafana → Explore → Tempo (filter by `service.name=rag-pipeline-api`)
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
2. Test the MCP endpoint directly:
   ```bash
   curl -X POST http://localhost:8000/mcp \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
   ```
3. Check API logs for import errors in `src/mcp/`

### Investigating errors (open-source observability)
- **Structured logs**: Grafana → Explore → Loki → `{job="rag-pipeline-api"} | json | level="error"`
- **Error rate metric**: Grafana → Explore → Prometheus → `rate(rag_jobs_failed_total[5m])`
- **Distributed traces**: Grafana → Explore → Tempo → filter by `status=error`

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

---

## Step 5: Update Environment Variables

### 5.1 Append Phase 7 variables to `apps/api/.env.example`

```env
# --- Phase 7: MCP, Observability, Auth ---

# JWT
JWT_SECRET=CHANGE-ME-IN-PRODUCTION
JWT_EXPIRY_HOURS=24
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=changeme

# OpenTelemetry (self-hosted Grafana Tempo)
OTEL_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=http://tempo:4317
OTEL_SERVICE_NAME=rag-pipeline-api

# Logging
LOG_FORMAT=console
LOG_LEVEL=INFO

# Rate Limiting
RATE_LIMIT=100/minute

# Grafana (self-hosted)
GRAFANA_ADMIN_PASSWORD=admin

# Environment
ENVIRONMENT=development
RELEASE_VERSION=1.0.0
```

---

## Done-When Checklist

| # | Criterion | Verify |
|---|-----------|--------|
| 1 | Re-ingestion detects changed documents | `ReingestionService().detect_changes(...)` correctly identifies added, updated, unchanged, and removed documents |
| 2 | Docker Compose prod overlay validates | `docker compose -f docker-compose.yml -f docker-compose.prod.yml config` succeeds |
| 3 | Health check endpoints work | `GET /health` → 200, `GET /health/ready` → 200 or 503 |
| 4 | README.md covers setup, architecture, MCP (Streamable HTTP), observability | File exists with complete sections |
| 5 | Runbook covers startup, common issues (including MCP troubleshooting and Grafana-based error investigation), manual overrides | File exists with all scenarios |
| 6 | `.env.example` contains all configuration for all 7 phases | File includes JWT, OTEL, logging, rate limit, Grafana vars — no paid service keys |

---

## Summary Report

Upon completion of this subtask, create a summary report at:
`rag-pipeline/ai-workspace/summary-reports/phase-7-subtask-4-production-hardening-summary.md`

The summary report must include:
- **Subtask**: Phase 7, Subtask 4 — Production Hardening
- **Status**: Complete / Partial / Blocked
- **Date**: {ISO 8601 date}
- **Files Created/Modified**: List every file path
- **Key Decisions**: Any deviations from the plan and why
- **Issues Encountered**: Problems and resolutions
- **Dependencies for Next Subtask**: What the next subtask needs to know
- **Verification Results**: Output of Done-When checklist items
