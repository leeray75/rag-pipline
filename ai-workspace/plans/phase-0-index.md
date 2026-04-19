# RAG Pipeline — Multi-Phase Implementation Index

> **Purpose**: Master index for AI coding agents. Each phase is a self-contained planning document optimized for a 32k context window LLM.
>
> **Project Root**: `rag-pipeline/`
>
> **Date**: 2026-04-14

---

## Technology Stack — Pinned Versions

Before starting ANY phase, verify these versions are still current by checking PyPI / npmjs.

### Python Backend

| Package | Version | Install | Phase |
|---|---|---|---|
| Python | 3.13.x | Runtime | 1 |
| FastAPI | 0.135.3 | `pip install "fastapi[standard]"` | 1 |
| Pydantic | 2.13.0 | `pip install pydantic` | 1 |
| SQLAlchemy | 2.0.49 | `pip install "sqlalchemy[asyncio]"` | 1 |
| Alembic | 1.18.4 | `pip install alembic` | 1 |
| Celery | 5.6.3 | `pip install celery` | 1 |
| Redis (broker) | 7.x | Docker image | 1 |
| qdrant-client | 1.17.1 | `pip install qdrant-client` | 1 |
| markitdown | 0.1.5 | `pip install markitdown` | 2 |
| Playwright | 1.58.0 | `pip install playwright` | 2 |
| BeautifulSoup4 | 4.14.3 | `pip install beautifulsoup4` | 2 |
| LangGraph | 1.1.6 | `pip install langgraph` | 3 |
| LangChain | 1.2.15 | `pip install langchain` | 3 |
| a2a-sdk | latest | `pip install a2a-sdk` | 4 |
| tiktoken | 0.12.0 | `pip install tiktoken` | 6 |
| FastEmbed | 0.8.0 | `pip install fastembed` | 6 |
| MCP Python SDK | 1.27.0 | `pip install mcp` | 7 |
| structlog | 25.4.0 | `pip install structlog` | 7 |
| opentelemetry-sdk | 1.33.0 | `pip install opentelemetry-sdk` | 7 |
| prometheus-fastapi-instrumentator | 7.1.0 | `pip install prometheus-fastapi-instrumentator` | 7 |
| python-jose | 3.4.0 | `pip install "python-jose[cryptography]"` | 7 |
| slowapi | 0.1.9 | `pip install slowapi` | 7 |
| langsmith | 0.3.42 | `pip install langsmith` | 7 |
| sentry-sdk | 2.29.1 | `pip install "sentry-sdk[fastapi]"` | 7 |

### Frontend

| Package | Version | Install |
|---|---|---|
| Next.js | 16.2.3 | `npx create-next-app@latest` |
| React | 19.2.5 | bundled with Next.js |
| Redux Toolkit | 2.11.2 | `npm install @reduxjs/toolkit react-redux` |
| TailwindCSS | 4.2.2 | `npm install tailwindcss` |
| shadcn/ui | latest | `npx shadcn@latest init` |
| TanStack Table | 9.x | `npm install @tanstack/react-table` |
| Vitest | 3.x | `npm install -D vitest` |

### Infrastructure

| Component | Version | Notes | Phase |
|---|---|---|---|
| Docker | 27.x+ | Docker Desktop or Engine | 1 |
| Docker Compose | 2.x | Compose V2 | 1 |
| Postgres | 17 | Docker image `postgres:17` | 1 |
| Redis | 7.x | Docker image `redis:7-alpine` | 1 |
| Qdrant | 1.13+ | Docker image `qdrant/qdrant:latest` | 1 |
| Turborepo | 2.x | `npm install -D turbo` | 1 |
| Traefik | 3.x | Docker image `traefik:v3.4` | 1 |
| Grafana | 11.6 | Docker image `grafana/grafana:11.6` | 7 |
| Grafana Tempo | 2.7 | Docker image `grafana/tempo:2.7` | 7 |
| Prometheus | 3.4 | Docker image `prom/prometheus:3.4` | 7 |
| Grafana Loki | 3.5 | Docker image `grafana/loki:3.5` | 7 |

---

## Phase Documents

| Phase | File | Description |
|---|---|---|
| **Phase 1** | [phase-1-foundation.md](phase-1-foundation.md) | Mono-repo setup, Docker Compose, FastAPI skeleton, Next.js scaffold, Postgres schemas, CI/CD |
| **Phase 2** | [phase-2-crawl-and-convert.md](phase-2-crawl-and-convert.md) | URL ingestion API, HTML fetching, doc discovery, markitdown conversion, staging file browser UI |
| **Phase 3** | [phase-3-audit-agent.md](phase-3-audit-agent.md) | LangGraph Audit Agent, document schema validation, quality assessment, report generation |
| **Phase 4** | [phase-4-correction-agent.md](phase-4-correction-agent.md) | LangGraph Correction Agent, A2A Protocol v1.0 agent servers, A2A client orchestrator, iterative audit-correct loop |
| **Phase 5** | [phase-5-human-review.md](phase-5-human-review.md) | Human review dashboard, Monaco editor, approval/rejection workflow |
| **Phase 6** | [phase-6-vector-ingestion.md](phase-6-vector-ingestion.md) | JSON chunking, embedding pipeline, Qdrant upsert, JSON review UI |
| **Phase 7** | [phase-7-mcp-and-hardening.md](phase-7-mcp-and-hardening.md) | MCP server tools, observability stack, auth, production hardening |

---

## Execution Rules for AI Coding Agents

1. **Execute phases sequentially** — each phase depends on the prior phase being complete
2. **Each phase document is self-contained** — read ONLY the current phase document plus this index
3. **Do NOT modify files from previous phases** unless explicitly instructed in the current phase
4. **Run the Done-When checklist** at the end of each phase before proceeding
5. **Pin versions exactly** as listed above — do not upgrade unless compatibility issues arise
6. **All paths are relative** to the mono-repo root `rag-pipeline/`
7. **Commit after each phase** with message format: `feat(phase-N): <description>`

---

## Mono-Repo Target Structure

```
rag-pipeline/
├── apps/
│   ├── api/                    # FastAPI backend (Python)
│   │   ├── src/
│   │   │   ├── agents/         # LangGraph agent definitions
│   │   │   ├── auth/           # JWT authentication (Phase 7)
│   │   │   ├── crawlers/       # URL + doc discovery
│   │   │   ├── converters/     # markitdown HTML to MD
│   │   │   ├── embeddings/     # FastEmbed model wrappers (Phase 6)
│   │   │   ├── ingest/         # Chunking + Qdrant upsert (Phase 6)
│   │   │   ├── mcp/            # MCP server tools (Phase 7)
│   │   │   ├── routers/        # FastAPI route modules
│   │   │   ├── models/         # SQLAlchemy models
│   │   │   ├── schemas/        # Pydantic schemas
│   │   │   ├── security/       # SSRF prevention (Phase 7)
│   │   │   ├── workers/        # Celery task definitions
│   │   │   └── main.py
│   │   ├── tests/
│   │   ├── alembic/
│   │   ├── data/staging/       # Chunk JSON staging area
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   └── alembic.ini
│   └── web/                    # Next.js frontend
│       ├── src/
│       │   ├── app/            # App Router pages
│       │   ├── components/     # Shared UI components
│       │   ├── features/       # Feature modules
│       │   ├── store/          # Redux store + RTK Query
│       │   └── lib/            # Shared utilities
│       ├── Dockerfile
│       ├── package.json
│       └── tsconfig.json
├── packages/
│   ├── shared-types/           # Shared TS + Python schemas
│   └── config/                 # Shared ESLint/TS configs
├── infra/
│   ├── docker-compose.yml
│   ├── docker-compose.dev.yml
│   ├── docker-compose.prod.yml  # Production overrides (Phase 7)
│   ├── traefik/
│   ├── prometheus/              # prometheus.yml (Phase 7)
│   ├── tempo/                   # tempo.yaml (Phase 7)
│   └── grafana/                 # Provisioning + dashboards (Phase 7)
├── .github/
│   └── workflows/
│       └── ci.yml
├── turbo.json
├── package.json
├── pnpm-workspace.yaml
└── ai-workspace/
    └── plans/                  # This directory
```

---

## Contract Artifacts

Each phase includes three contract artifacts for implementation validation and rollback:

| Phase | contracts.json | validation.sh | rollback.sh |
|---|---|---|---|
| **Phase 1** | [phase-1/contracts.json](phase-1/contracts.json) | [phase-1/validation.sh](phase-1/validation.sh) | [phase-1/rollback.sh](phase-1/rollback.sh) |
| **Phase 2** | [phase-2/contracts.json](phase-2/contracts.json) | [phase-2/validation.sh](phase-2/validation.sh) | [phase-2/rollback.sh](phase-2/rollback.sh) |
| **Phase 3** | [phase-3/contracts.json](phase-3/contracts.json) | [phase-3/validation.sh](phase-3/validation.sh) | [phase-3/rollback.sh](phase-3/rollback.sh) |
| **Phase 4** | [phase-4/contracts.json](phase-4/contracts.json) | [phase-4/validation.sh](phase-4/validation.sh) | [phase-4/rollback.sh](phase-4/rollback.sh) |
| **Phase 5** | [phase-5/contracts.json](phase-5/contracts.json) | [phase-5/validation.sh](phase-5/validation.sh) | [phase-5/rollback.sh](phase-5/rollback.sh) |
| **Phase 6** | [phase-6/contracts.json](phase-6/contracts.json) | [phase-6/validation.sh](phase-6/validation.sh) | [phase-6/rollback.sh](phase-6/rollback.sh) |
| **Phase 7** | [phase-7/contracts.json](phase-7/contracts.json) | [phase-7/validation.sh](phase-7/validation.sh) | [phase-7/rollback.sh](phase-7/rollback.sh) |

### Artifact Descriptions

- **`contracts.json`** — Specifies every class/function/type that must be exported, every external dependency and its version pin, the exact signature of each function (params + return types), database tables, API endpoints, and Docker services for the phase.

- **`validation.sh`** — A bash script the implementing agent runs after completing a phase to verify:
  - All expected files exist
  - All expected Python/TypeScript exports are present (via import checks)
  - Type checking passes (mypy for Python, tsc for TypeScript)
  - Phase-specific tests pass
  - Router registrations are in place
  - No orphaned imports

- **`rollback.sh`** — A bash script that reverts the phase if validation fails:
  - Searches for phase commits by `feat(phase-N):` message pattern
  - Falls back to file-based removal if no commits found
  - Creates a safety branch before any destructive operation
  - Requires interactive confirmation before git reset

### Usage

```bash
# After implementing Phase N, validate:
bash rag-pipeline/ai-workspace/plans/phase-N/validation.sh

# If validation fails, rollback:
bash rag-pipeline/ai-workspace/plans/phase-N/rollback.sh
```

---

## Subtask Breakdown Reference

> Each phase has been decomposed into smaller, self-contained subtask plans optimized for a **32k context window**. Each subtask document includes all necessary context, code blocks, and instructions — no need to reference the parent phase document.
>
> **Summary Reports**: At the end of each subtask, the AI agent creates a summary report in `rag-pipeline/ai-workspace/summary-reports/` that can be referenced by future subtasks.

### Phase 1 — Foundation (5 subtasks)

| Subtask | File | Scope |
|---|---|---|
| 1-1 | [phase-1-subtask-1-monorepo-init.md](phase-1/subtasks/phase-1-subtask-1-monorepo-init.md) | Root package.json, pnpm-workspace, turbo.json, .gitignore, pnpm install |
| 1-2 | [phase-1-subtask-2-fastapi-and-database.md](phase-1/subtasks/phase-1-subtask-2-fastapi-and-database.md) | pyproject.toml, FastAPI app, config, database, health router, SQLAlchemy models, Alembic migrations |
| 1-3 | [phase-1-subtask-3-nextjs-and-schemas.md](phase-1/subtasks/phase-1-subtask-3-nextjs-and-schemas.md) | Next.js scaffold, shadcn/ui, Redux store, RTK Query, Pydantic schemas |
| 1-4 | [phase-1-subtask-4-docker-celery-cicd.md](phase-1/subtasks/phase-1-subtask-4-docker-celery-cicd.md) | Docker Compose (7 services), Dockerfiles, Celery app, GitHub Actions CI |
| 1-5 | [phase-1-subtask-5-tests-and-validation.md](phase-1/subtasks/phase-1-subtask-5-tests-and-validation.md) | conftest.py, test_health.py, ruff/mypy checks, Done-When validation |

### Phase 2 — Crawl & Convert (4 subtasks)

| Subtask | File | Scope |
|---|---|---|
| 2-1 | [phase-2-subtask-1-fetcher-and-discovery.md](phase-2/subtasks/phase-2-subtask-1-fetcher-and-discovery.md) | Phase 2 deps, URL fetcher (httpx + Playwright), link discovery (CSS + LLM) |
| 2-2 | [phase-2-subtask-2-converter-and-celery.md](phase-2/subtasks/phase-2-subtask-2-converter-and-celery.md) | Markdown converter (markitdown + sanitization), Celery task chain |
| 2-3 | [phase-2-subtask-3-api-and-websocket.md](phase-2/subtasks/phase-2-subtask-3-api-and-websocket.md) | Jobs API router, WebSocket progress streaming |
| 2-4 | [phase-2-subtask-4-frontend-and-tests.md](phase-2/subtasks/phase-2-subtask-4-frontend-and-tests.md) | RTK Query jobs API, staging browser UI, tests |

### Phase 3 — Audit Agent (3 subtasks)

| Subtask | File | Scope |
|---|---|---|
| 3-1 | [phase-3-subtask-1-schema-validator-and-agent.md](phase-3/subtasks/phase-3-subtask-1-schema-validator-and-agent.md) | LangGraph/LangChain deps, schema validator (10 rules), 6-node audit agent graph |
| 3-2 | [phase-3-subtask-2-audit-api-endpoints.md](phase-3/subtasks/phase-3-subtask-2-audit-api-endpoints.md) | Audit API router (3 endpoints), router registration |
| 3-3 | [phase-3-subtask-3-audit-ui-and-tests.md](phase-3/subtasks/phase-3-subtask-3-audit-ui-and-tests.md) | RTK Query audit API, audit report viewer UI, 7 pytest tests |

### Phase 4 — Correction Agent (3 subtasks)

| Subtask | File | Scope |
|---|---|---|
| 4-1 | [phase-4-subtask-1-a2a-protocol-and-correction-agent.md](phase-4/subtasks/phase-4-subtask-1-a2a-protocol-and-correction-agent.md) | a2a-sdk, AgentCards, A2A helpers, correction agent graph, A2A server wrappers for audit + correction |
| 4-2 | [phase-4-subtask-2-loop-orchestrator-and-api.md](phase-4/subtasks/phase-4-subtask-2-loop-orchestrator-and-api.md) | A2A client orchestrator, loop API endpoints, agent discovery endpoints |
| 4-3 | [phase-4-subtask-3-loop-ui-and-tests.md](phase-4/subtasks/phase-4-subtask-3-loop-ui-and-tests.md) | Loop monitoring UI with A2A task states, A2A helper + agent card tests |

### Phase 5 — Human Review (3 subtasks)

| Subtask | File | Scope |
|---|---|---|
| 5-1 | [phase-5-subtask-1-models-api-and-deps.md](phase-5/subtasks/phase-5-subtask-1-models-api-and-deps.md) | Frontend deps, ReviewDecision/Comment models, review API (8 endpoints) |
| 5-2 | [phase-5-subtask-2-review-dashboard-ui.md](phase-5/subtasks/phase-5-subtask-2-review-dashboard-ui.md) | RTK Query review API, dashboard UI, Monaco editor, diff view |
| 5-3 | [phase-5-subtask-3-tests-and-validation.md](phase-5/subtasks/phase-5-subtask-3-tests-and-validation.md) | Review API tests, Phase 5 Done-When validation |

### Phase 6 — Vector Ingestion (5 subtasks)

| Subtask | File | Scope |
|---|---|---|
| 6-1 | [phase-6-subtask-1-deps-chunking-embedding.md](phase-6/subtasks/phase-6-subtask-1-deps-chunking-embedding.md) | fastembed + tiktoken deps, MarkdownChunker, FastEmbedService |
| 6-2 | [phase-6-subtask-2-schemas-models-pipeline.md](phase-6/subtasks/phase-6-subtask-2-schemas-models-pipeline.md) | Chunk/collection schemas, ChunkRecord/VectorCollection models, ChunkingPipeline |
| 6-3 | [phase-6-subtask-3-qdrant-celery-api.md](phase-6/subtasks/phase-6-subtask-3-qdrant-celery-api.md) | QdrantIngestService, Celery tasks, ingest API router (10 endpoints) |
| 6-4 | [phase-6-subtask-4-rtk-chunk-browser-embed-ui.md](phase-6/subtasks/phase-6-subtask-4-rtk-chunk-browser-embed-ui.md) | RTK Query ingest API, ChunkBrowser, EmbedToQdrant UI |
| 6-5 | [phase-6-subtask-5-ingest-page-env-tests-validation.md](phase-6/subtasks/phase-6-subtask-5-ingest-page-env-tests-validation.md) | Ingest page route, env vars, test suite, Done-When validation |

### Phase 7 — MCP & Hardening (5 subtasks)

| Subtask | File | Scope |
|---|---|---|
| 7-1 | [phase-7-subtask-1-mcp-server-tools.md](phase-7/subtasks/phase-7-subtask-1-mcp-server-tools.md) | Phase 7 deps, MCP server with 7 tools, SSE/stdio transport |
| 7-2 | [phase-7-subtask-2-observability-stack.md](phase-7/subtasks/phase-7-subtask-2-observability-stack.md) | structlog, OpenTelemetry, Prometheus metrics, Grafana/Tempo/Loki infra |
| 7-3 | [phase-7-subtask-3-auth-and-security.md](phase-7/subtasks/phase-7-subtask-3-auth-and-security.md) | JWT auth, rate limiting, SSRF prevention |
| 7-4 | [phase-7-subtask-4-production-hardening.md](phase-7/subtasks/phase-7-subtask-4-production-hardening.md) | Re-ingestion delta, docker-compose.prod.yml, health checks, README, runbook |
| 7-5 | [phase-7-subtask-5-langsmith-sentry-tests-validation.md](phase-7/subtasks/phase-7-subtask-5-langsmith-sentry-tests-validation.md) | LangSmith tracing, Sentry integration, tests, Done-When validation |

### Total: 28 subtasks across 7 phases
