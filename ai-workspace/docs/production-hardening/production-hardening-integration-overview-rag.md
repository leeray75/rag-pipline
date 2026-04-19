# Production Hardening Integration Overview — RAG Reference Document

<!-- RAG_METADATA
topic: production-hardening, integration, architecture
stack: docker-compose + sqlalchemy + alembic + fastapi + pytest
version: phase-7-subtasks-4-and-5
tags: production, hardening, health-checks, re-ingestion, testing, main.py, open-source
use_case: phase-7-subtask-4-production-hardening, phase-7-subtask-5-tests-validation
-->

## Overview

This document covers the integration of all production hardening components across Phase 7 Subtasks 4 and 5. **All tools are open-source and self-hosted — no paid SaaS services.**

| Subtask | Components |
|---|---|
| **Subtask 4** | Re-ingestion delta detection, Docker Compose prod overlay, health check endpoints, README + runbook, env vars |
| **Subtask 5** | Integration tests (MCP, auth, SSRF, health, re-ingestion), Phase 7 validation |

### Observability (Open-Source Only)

| Need | Solution |
|---|---|
| Agent run traces | OpenTelemetry → Grafana Tempo (Subtask 2) |
| Error logs | structlog JSON → Grafana Loki (Subtask 2) |
| Error rate metrics | `rag_jobs_failed_total` counter → Prometheus → Grafana (Subtask 2) |
| Distributed tracing | OTel spans across FastAPI + Celery + httpx (Subtask 2) |

---

## Complete `main.py` Initialization Order

The order of initialization in `src/main.py` is critical. All components must be initialized in this exact sequence:

```python
# ============================================================
# 1. LOGGING — Must be first, before any imports that log
# ============================================================
from src.logging_config import configure_logging
configure_logging()

import structlog
log = structlog.get_logger(__name__)

# ============================================================
# 2. FASTAPI APP CREATION
# ============================================================
from fastapi import FastAPI
app = FastAPI(
    title="RAG Pipeline API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ============================================================
# 3. OPENTELEMETRY — After app creation, before middleware
# ============================================================
from src.telemetry import configure_telemetry
configure_telemetry(app)

# ============================================================
# 4. PROMETHEUS METRICS — After app creation
# ============================================================
from src.metrics import configure_metrics
configure_metrics(app)

# ============================================================
# 5. ROUTERS — Health first (required for Docker healthcheck)
# ============================================================
from src.routers.health import router as health_router
from src.routers.jobs import router as jobs_router
from src.routers.chunks import router as chunks_router
from src.mcp.http_transport import router as mcp_router

app.include_router(health_router)                          # /health, /health/ready
app.include_router(jobs_router, prefix="/api/v1")
app.include_router(chunks_router, prefix="/api/v1")
app.include_router(mcp_router)                             # POST /mcp

log.info("application_started", version="1.0.0")
```

---

## Environment Variables — Complete Reference

```env
# ============================================================
# Phase 7: MCP, Observability, Auth, Production
# ============================================================

# JWT Authentication
JWT_SECRET=CHANGE-ME-IN-PRODUCTION
JWT_EXPIRY_HOURS=24
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=changeme

# OpenTelemetry (self-hosted Grafana Tempo)
OTEL_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=http://tempo:4317
OTEL_SERVICE_NAME=rag-pipeline-api

# Logging
LOG_FORMAT=console          # "json" for production
LOG_LEVEL=INFO

# Rate Limiting
RATE_LIMIT=100/minute

# Grafana (self-hosted)
GRAFANA_ADMIN_PASSWORD=admin

# Environment
ENVIRONMENT=development     # "production" for prod
RELEASE_VERSION=1.0.0
```

---

## Re-Ingestion Delta Detection Architecture

```
New fetch results
    │
    ▼
ReingestionService.detect_changes()
    │
    ├── Load existing Documents from DB (by job_id)
    ├── Compute SHA-256 hash of new content
    ├── Compare hashes:
    │   ├── URL not in DB → added[]
    │   ├── Hash changed → updated[]
    │   ├── Hash same → unchanged[]
    │   └── URL in DB but not in new → removed[]
    │
    ▼
Return delta: {added, updated, unchanged, removed}
    │
    ▼
For updated/removed: invalidate_chunks()
    │
    ▼
Re-run pipeline for added + updated documents only
```

**Key**: The `content_hash` column (SHA-256, 64 chars) on the `Document` model enables this. Added in Phase 7 Subtask 4 via Alembic migration.

---

## File Inventory — Subtask 4

| File | Purpose |
|---|---|
| `apps/api/src/ingest/reingestion.py` | Delta detection service |
| `apps/api/src/models/document.py` | Add `content_hash: Mapped[str \| None]` column |
| `apps/api/alembic/versions/xxxx_add_content_hash.py` | Migration: add content_hash |
| `infra/docker-compose.prod.yml` | Production resource limits + healthchecks |
| `apps/api/src/routers/health.py` | `/health` and `/health/ready` endpoints |
| `README.md` | Project overview, quick start, MCP docs |
| `docs/runbook.md` | Operations runbook (Grafana-based error investigation) |
| `apps/api/.env.example` | All Phase 7 env vars (no paid service keys) |

---

## File Inventory — Subtask 5

| File | Purpose |
|---|---|
| `apps/api/tests/test_mcp_server.py` | MCP tool registration tests |
| `apps/api/tests/test_mcp_http_transport.py` | MCP HTTP endpoint tests |
| `apps/api/tests/test_auth.py` | JWT auth tests |
| `apps/api/tests/test_url_validator.py` | SSRF prevention tests |
| `apps/api/tests/test_health.py` | Health check endpoint tests |
| `apps/api/tests/test_reingestion.py` | Delta detection unit tests |

---

## Docker Compose Production Deployment

```bash
# Validate merged config (no errors = valid)
docker compose -f docker-compose.yml -f infra/docker-compose.prod.yml config

# Deploy production stack
docker compose -f docker-compose.yml -f infra/docker-compose.prod.yml up -d

# Check service health
docker compose ps

# View logs
docker compose logs -f api

# Run migrations before starting
docker compose exec api alembic upgrade head
```

---

## Health Check Verification

```bash
# Liveness (always 200 if process is running)
curl http://localhost:8000/health
# → {"status": "ok"}

# Readiness (200 if all deps OK, 503 if degraded)
curl http://localhost:8000/health/ready
# → {"status": "ready", "checks": {"postgres": "ok", "redis": "ok", "qdrant": "ok"}}
```

---

## Test Execution

```bash
cd rag-pipeline/apps/api

# Run all Phase 7 tests
python -m pytest tests/ -v

# Run specific test files
python -m pytest tests/test_mcp_server.py -v
python -m pytest tests/test_mcp_http_transport.py -v
python -m pytest tests/test_auth.py -v
python -m pytest tests/test_url_validator.py -v
python -m pytest tests/test_health.py -v
python -m pytest tests/test_reingestion.py -v

# Run with coverage
python -m pytest tests/ --cov=src --cov-report=term-missing
```

---

## Investigating Errors (Open-Source Observability)

```bash
# View error logs in Grafana Loki
# Grafana → Explore → Loki → query:
# {job="rag-pipeline-api"} | json | level="error"

# View error rate in Prometheus
# Grafana → Explore → Prometheus → query:
# rate(rag_jobs_failed_total[5m])

# View distributed traces in Grafana Tempo
# Grafana → Explore → Tempo → filter: status=error, service.name=rag-pipeline-api

# View agent run spans
# Grafana → Explore → Tempo → filter: service.name=rag-pipeline-api
```

---

## Phase 7 Complete Done-When Checklist

| # | Criterion | Component |
|---|---|---|
| 1 | MCP server lists 7 tools | Subtask 1 |
| 2 | MCP `search_knowledge_base` returns Qdrant results | Subtask 1 |
| 3 | Streamable HTTP at `POST /mcp` works | Subtask 1 |
| 4 | Structured JSON logs in production | Subtask 2 |
| 5 | OTel traces in Grafana Tempo | Subtask 2 |
| 6 | Prometheus `/metrics` has `rag_*` counters | Subtask 2 |
| 7 | Grafana dashboard shows pipeline throughput | Subtask 2 |
| 8 | Agent run spans visible in Grafana Tempo | Subtask 2 |
| 9 | Error logs searchable in Grafana Loki | Subtask 2 |
| 10 | JWT auth protects sensitive endpoints | Subtask 3 |
| 11 | Rate limiting returns 429 | Subtask 3 |
| 12 | SSRF prevention blocks private IPs | Subtask 3 |
| 13 | Re-ingestion detects changed documents | Subtask 4 |
| 14 | Health check endpoints work | Subtask 4 |
| 15 | Docker Compose prod overlay validates | Subtask 4 |
| 16 | README + runbook complete | Subtask 4 |
| 17 | All Phase 7 tests pass | Subtask 5 |

---

## Common Integration Pitfalls

1. **Initialization order** — `configure_logging()` must be called before any `structlog.get_logger()` call. `configure_telemetry(app)` must be called after `app = FastAPI(...)`.
2. **`content_hash` migration** — Must run `alembic upgrade head` before starting the API after adding the `content_hash` column.
3. **Test isolation** — Set `OTEL_ENABLED=false` in `conftest.py` to prevent test traces from being sent to Tempo.
4. **MCP internal API** — Use `mcp.handle_request(ListToolsRequest(...))`, not `mcp._tool_handlers["list_tools"]()`.
5. **Docker healthcheck vs readiness** — Use `/health` (liveness) for Docker `healthcheck`, not `/health/ready`. Readiness may fail during startup.
6. **`start_period` in healthcheck** — Without this, Docker marks the container unhealthy during the startup grace period.

---

## Sources
- https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html (SQLAlchemy async)
- https://alembic.sqlalchemy.org/en/latest/ (Alembic)
- https://pytest-asyncio.readthedocs.io/en/latest/ (pytest-asyncio)
- https://docs.docker.com/compose/compose-file/ (Docker Compose V2)
- https://fastapi.tiangolo.com/tutorial/testing/ (FastAPI testing)
