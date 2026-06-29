# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A production-grade RAG (Retrieval-Augmented Generation) document ingestion pipeline. It crawls documentation websites, converts HTML to Markdown, validates quality via AI agents, and ingests into Qdrant for vector search.

Pipeline flow: `URL → Fetch → Convert → Audit Agent → Correction Agent → Human Review → Chunk → Embed → Qdrant`

## Monorepo Structure

This is a Turborepo/pnpm monorepo:
- `apps/api/` — FastAPI backend (Python 3.13)
- `apps/web/` — Next.js 16.2 frontend (React 19, Redux Toolkit)
- `infra/` — Docker Compose, Traefik, Grafana/Prometheus/Tempo/Loki configs

## Commands

### Root (Turborepo)
```bash
pnpm dev          # Start both API and web dev servers
pnpm build        # Build all apps
pnpm test         # Run all tests
pnpm lint         # Lint all apps
```

### API (from `apps/api/`)
```bash
pip install -e ".[dev]"           # Install with dev dependencies
playwright install chromium       # Required for Playwright crawler

# Linting & type checking
ruff check src/ tests/
mypy src/

# Tests
pytest tests/ -v                  # All tests
pytest tests/test_health.py -v    # Single test file
pytest tests/ -k "test_name" -v   # Single test by name

# Database migrations
alembic upgrade head
alembic revision --autogenerate -m "description"
alembic downgrade -1

# Run API server directly
uvicorn src.main:app --reload --port 8000

# Run Celery worker
celery -A src.workers.celery_app worker --loglevel=info

# Run Celery Beat (periodic tasks)
celery -A src.workers.celery_app beat --loglevel=info
```

### Web (from `apps/web/`)
```bash
pnpm install
pnpm dev          # Next.js dev server (port 3000)
pnpm build
pnpm lint         # eslint
pnpm tsc --noEmit # Type-check
pnpm vitest run   # Tests
```

### Infrastructure
```bash
# Start all services (dev)
docker compose -f ./infra/docker-compose.yml up -d

# Production
docker compose -f ./infra/docker-compose.yml -f ./infra/docker-compose.prod.yml up -d

# Run migrations in Docker
docker compose exec api alembic upgrade head
```

## Architecture

### API (`apps/api/src/`)

All settings are loaded from environment variables prefixed `RAG_` via `src/config.py` (pydantic-settings). The key config file is `apps/api/.env.example`.

**Routers** (`src/routers/`): FastAPI routers mounted at `/api/v1/`:
- `jobs` — CRUD for ingestion jobs, retry endpoint
- `audit` — trigger audit workflow, fetch reports
- `loop` — trigger A2A audit-correct loop
- `review` — human review decisions (approve/reject documents)
- `ingest` — chunk and embed endpoints
- `websocket` — real-time job progress updates
- `auth` — JWT login at `/api/v1/auth/login`
- `a2a_discovery` — A2A agent card discovery

**Workers** (`src/workers/`): Celery tasks using Redis as broker/backend:
- `crawl_tasks.py` — `crawl_url_task`, `fetch_and_convert_task`, `finalize_crawl_task`. Uses Celery chord for parallel page fetching. All tasks extend `CrawlBaseTask` to update job status on failure.
- `ingest_tasks.py` — chunking and embedding tasks
- `celery_app.py` — Celery app config; explicitly imports `crawl_tasks` to register `crawl.*` tasks (required — do not remove this import)

**Agents** (`src/agents/`):
- `audit_agent.py` — LangGraph 6-node workflow: `load_documents → validate_schema → assess_quality → check_duplicates → compile_report → save_report`
- `correction_agent.py` — LangGraph workflow that fixes documents flagged by the audit agent
- `a2a_loop_orchestrator.py` — A2A protocol client that runs the iterative audit↔correct loop (up to 10 rounds)
- `a2a_audit_server.py` / `a2a_correction_server.py` — A2A server implementations mounted at `/a2a/audit` and `/a2a/correction` during lifespan

**Database** (`src/database.py`): Two engines — async (`asyncpg`) for FastAPI routes, sync (`psycopg2`) for Celery workers. Never use the async engine in Celery tasks.

**Models** (`src/models/`):
- `chunk.py` — `IngestionJob`, `ChunkRecord`, `VectorCollection`, `JobStatus` enum
- `document.py` — `Document`
- `audit.py` — `AuditReport`
- `review.py` — `ReviewDecision`

**MCP** (`src/mcp/`): FastMCP server with stateless HTTP transport, mounted at `/` so clients POST to `http://host:8000/mcp`. Tools: `ingest_url`, `get_job_status`, `list_documents`, `get_audit_report`, `search_knowledge_base`, `approve_job`, `get_collection_stats`.

**Crawlers** (`src/crawlers/`):
- `fetcher.py` — `fetch_url()` supports both static (httpx) and browser (Playwright) modes
- `link_discovery.py` — discovers doc links via CSS selectors with LLM fallback

**Ingest** (`src/ingest/`):
- `chunker.py` — tiktoken-aware chunking with heading path tracking
- `qdrant_ingest.py` — upserts chunks into Qdrant
- `reingestion.py` — handles re-embedding existing chunks

**Staging**: Crawled HTML and converted Markdown are stored at `/app/data/staging/{job_id}/html/` and `/app/data/staging/{job_id}/markdown/` inside the container.

### Web (`apps/web/src/`)

Next.js 16 App Router. Read `node_modules/next/dist/docs/` before writing any Next.js code — this version has breaking API changes.

**Pages** (`src/app/`): `jobs/`, `audit/[jobId]`, `review/[jobId]/[docId]`, `loop/[jobId]`, `ingestion/`, `staging/`

**State**: Redux Toolkit with RTK Query. API slices live in `src/store/api/` (jobs-api, audit-api, review-api, loop-api) and `src/store/ingestApi.ts`. Use the typed hooks from `src/store/hooks.ts`.

**UI**: shadcn/ui components in `src/components/ui/`. Monaco editor used in the review page for document editing with diff view.

### LLM Integration

The API uses an OpenAI-compatible endpoint (not Anthropic). Default: `qwen3.6-35b-a3b` via `RAG_LLM_ENDPOINT`. LangChain's `ChatOpenAI` is used with the custom endpoint.

### Observability

- Traces: OpenTelemetry → Grafana Tempo (`http://localhost:3200`)
- Metrics: Prometheus → Grafana (`http://localhost:3001`)
- Logs: structlog → Loki (`http://localhost:3100`)
- Service name: `rag-pipeline-api`

### Alembic Migrations

Migration files are in `apps/api/alembic/versions/`. The `down_revision` chain must be kept intact — check existing migrations before creating new ones to ensure the chain is correct.

### CI

GitHub Actions (`.github/workflows/ci.yml`) runs on push/PR to `main`:
1. API: `ruff check` → `mypy` → `pytest` (requires live Postgres)
2. Web: `eslint` → `tsc --noEmit` → `vitest run`
3. Docker build (after lint/test pass)
