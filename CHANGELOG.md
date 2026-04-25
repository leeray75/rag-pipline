# Changelog

All notable changes to the RAG Pipeline project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.2.0] - 2026-04-25

### Added

#### A2A Protocol v1.0.2 SDK Integration
- Updated A2A Python SDK to v1.0.2 with full compatibility
- Created [`a2a_servers.py`](rag-pipline/apps/api/src/agents/a2a_servers.py) for server instances with new `DefaultRequestHandler` pattern
- Created [`a2a_audit_server.py`](rag-pipline/apps/api/src/agents/a2a_audit_server.py) with `AgentExecutor` interface implementation
- Created [`a2a_correction_server.py`](rag-pipline/apps/api/src/agents/a2a_correction_server.py) with `AgentExecutor` interface implementation
- Created [`a2a_helpers.py`](rag-pipline/apps/api/src/agents/a2a_helpers.py) with protobuf-compatible helper functions
- Created [`a2a_agent_cards.py`](rag-pipline/apps/api/src/agents/a2a_agent_cards.py) with updated `AgentCard` structure using `supported_interfaces`
- Created [`a2a_loop_orchestrator.py`](rag-pipline/apps/api/src/agents/a2a_loop_orchestrator.py) with `ClientFactory` pattern
- Updated [`a2a_discovery.py`](rag-pipline/apps/api/src/routers/a2a_discovery.py) with `.well-known/agent-card.json` endpoints
- Updated [`loop.py`](rag-pipline/apps/api/src/routers/loop.py) to use new client API
- Updated [`main.py`](rag-pipline/apps/api/src/main.py) to mount A2A routes at `/a2a/audit` and `/a2a/correction`
- Updated [`config.py`](rag-pipline/apps/api/src/config.py) with A2A configuration settings

#### Configuration
- Added `a2a_base_url` setting (default: `http://localhost:8000`)
- Added `a2a_streaming_enabled` setting (default: `true`)
- Added `a2a_push_notifications_enabled` setting (default: `false`)

#### Infrastructure
- Updated [`traefik-config.yml`](rag-pipline/infra/traefik-config.yml) with A2A routers for `/a2a/audit` and `/a2a/correction`
- Updated [`docker-compose.yml`](rag-pipline/infra/docker-compose.yml) with A2A Traefik labels
- Updated [`docker-compose.dev.yml`](rag-pipline/infra/docker-compose.dev.yml) with full A2A configuration

#### Testing
- Updated [`test_a2a_helpers.py`](rag-pipline/apps/api/tests/test_a2a_helpers.py) with protobuf-compatible tests
- All 9 A2A helper tests passing

### Changed

#### SDK API Migration
- `A2AClient` → `Client` via `ClientFactory`
- `A2AServer` → `DefaultRequestHandler` with `create_jsonrpc_routes()`
- `AgentCard.url` → `AgentCard.supported_interfaces` with `AgentInterface`
- `AgentCapabilities.pushNotifications` → `AgentCapabilities.push_notifications`
- `Role.user`/`Role.agent` → `Role.ROLE_USER`/`Role.ROLE_AGENT`
- `TaskState.submitted` → `TaskState.TASK_STATE_SUBMITTED` (and other states)
- `TaskStatus.timestamp` now requires protobuf `Timestamp` object

#### Field Naming Conventions
- All Protocol Buffer fields now use snake_case:
  - `taskId` → `task_id`
  - `messageId` → `message_id`
  - `artifactId` → `artifact_id`
  - `contextId` → `context_id`
  - `supportedInterfaces` → `supported_interfaces`

#### Protobuf Type Requirements
- `Part.data` now requires protobuf `Value` type (use `json_format.ParseDict()`)
- `TaskStatus.timestamp` now requires protobuf `Timestamp` type (use `Timestamp.FromDatetime()`)

### Fixed

- Fixed `ValueError` for Protocol Buffer field naming (snake_case required)
- Fixed `AttributeError` for protobuf message immutability
- Fixed `TypeError` for timestamp field type requirements

### Removed

- Deprecated `A2AClient` class (replaced by `Client` via `ClientFactory`)
- Deprecated `A2AServer` class (replaced by `DefaultRequestHandler` pattern)

---

## [0.1.1] - 2026-04-23

## [0.1.1] - 2026-04-23

### Fixed

- Fixed `ERR_CONNECTION_REFUSED` error by adding missing SQLAlchemy ORM models
- Added missing `Base` class to `src/database.py` for model inheritance
- Created missing model files:
  - `src/models/__init__.py`: Module exports
  - `src/models/chunk.py`: `ChunkRecord`, `VectorCollection`, `IngestionJob`, `JobStatus`
  - `src/models/document.py`: `Document`
  - `src/models/review.py`: `ReviewComment`, `ReviewDecision`
  - `src/models/audit.py`: `AuditReport`

### Changed

- Updated `src/models/__init__.py` to export all new models
- Updated `src/database.py` to export `Base` class

---

## [0.1.0] - 2026-04-15

### Added - Phase 1 Foundation (Subtasks 1-5)

#### Subtask 1: Monorepo Initialization
- Added Turborepo for task orchestration
- Configured PNPM workspaces for monorepo structure
- Created root `package.json` with scripts for build, dev, test, lint
- Added `.gitignore` for Node.js/Python projects
- Initialized `turbo.json` with pipeline configurations

#### Subtask 2: FastAPI Backend & Database
- Created FastAPI application scaffold (`apps/api/src/main.py`)
- Implemented SQLAlchemy async database engine with connection pooling
- Added Alembic for database migrations
- Created 4 database models:
  - `IngestionJob`: Tracks pipeline jobs through the ingestion lifecycle
  - `Document`: Represents a single documentation page within a job
  - `AuditReport`: Stores validation results from audit agent rounds
  - `VectorCollection`: Tracks Qdrant collections created by the pipeline
- Implemented health check endpoint at `/api/v1/health`
- Added configuration management using Pydantic-Settings

#### Subtask 3: Next.js Frontend & Schemas
- Scaffolding Next.js 16.2.3 application with App Router
- Integrated shadcn/ui component library (New York style)
- Implemented Redux Toolkit with RTK Query for state management
- Created shared Pydantic schemas:
  - `JobCreate`, `JobResponse`, `JobStatusResponse` for job management
  - `DocumentResponse` for document data transfer
- Added shadcn/ui components: button, card, input, badge, tabs, separator
- Configured frontend to connect to API at `http://localhost:8000/api/v1`

#### Subtask 4: Docker Compose & CI/CD
- Created Docker Compose configuration with 7 services:
  - Traefik (reverse proxy)
  - FastAPI Backend
  - Next.js Frontend
  - Celery Worker
  - PostgreSQL 17
  - Redis 7 (message broker)
  - Qdrant (vector database)
- Implemented multi-stage Docker builds for optimized images
- Created CI/CD pipeline (`.github/workflows/ci.yml`) with:
  - Python linting (ruff) and type-checking (mypy)
  - Web linting and type-checking
  - Pytest and Vitest execution
  - Docker image building
- Added development override for hot reloading

#### Subtask 5: Tests & Validation
- Created pytest test suite with:
  - Async HTTP test client fixture (`tests/conftest.py`)
  - Health endpoint validation tests (`tests/test_health.py`)
- Implemented validation script for Phase 1 completion
- Configured ruff and mypy for code quality checks
- Added `.dockerignore` files for optimized builds

### Technical Architecture
- **Monorepo Structure**: Applications and shared packages
- **Backend**: FastAPI with async SQLAlchemy, Alembic migrations
- **Frontend**: Next.js 16 with App Router, Redux, shadcn/ui
- **Infrastructure**: Docker Compose with Traefik reverse proxy
- **Task Queue**: Celery with Redis broker
- **Database**: PostgreSQL for relational data
- **Vector Store**: Qdrant for vector embeddings

### Breaking Changes
None

### Deprecations
None

### Known Issues
- Existing source code has minor linting issues (SQLAlchemy forward references, missing trailing newlines, import ordering)
- mypy type checking shows expected warnings for:
  - Missing type stubs for Celery (known issue)
  - SQLAlchemy forward references in relationships (intentional)
  - Minor type arguments in routers (non-blocking)

### Migration Notes
- Database migration: Run `alembic upgrade head` to create all tables
- Environment variables: Copy `.env.example` to `.env` and configure
- API base URL: Configure `NEXT_PUBLIC_API_URL` in frontend `.env.local`

### Validation Checklist
To verify Phase 1 completion, ensure:
- [ ] `pnpm install` completes successfully at monorepo root
- [ ] `docker compose -f infra/docker-compose.yml up --build` starts all 7 services
- [ ] Health endpoint returns `200` with `{"status": "healthy", "service": "rag-pipeline-api", "version": "0.1.0"}`
- [ ] PostgreSQL migrations run cleanly via `alembic upgrade head`
- [ ] Next.js dashboard loads at `http://localhost:3000` with placeholder cards
- [ ] Redis is reachable (redis-cli ping returns PONG)
- [ ] Qdrant dashboard accessible at `http://localhost:6333/dashboard`
- [ ] Celery worker starts and connects to Redis broker
- [ ] pytest passes with `pytest tests/ -v`

---

## [0.2.0] - 2026-04-23

### Added - Phase 6: Embedding Pipeline & Ingestion UI

- **Chunking Engine**: Created `MarkdownChunker` with tiktoken-aware chunking and heading-path tracking
- **Embedding Service**: Created `FastEmbedService` for local ONNX embeddings (BAAI/bge-small-en-v1.5)
- **Qdrant Integration**: Created `QdrantIngestService` for embedding and upserting chunks
- **Ingestion API Router**: Added 8 endpoints for chunking, embedding, collections, and search
- **Frontend Components**: Created `ChunkBrowser.tsx` and `EmbedToQdrant.tsx` UI components
- **Database Models**: Added `ChunkRecord` and `VectorCollection` models
- **Database Migration**: Added `2026_04_18_1708_add_chunks_and_update_vector_collections.py`

### Added - Phase 7: Production Hardening & MCP Server

- **MCP Server**: Implemented FastMCP server with 7 tools (ingest_url, get_job_status, list_documents, get_audit_report, search_knowledge_base, approve_job, get_collection_stats)
- **Observability Stack**: Integrated OpenTelemetry traces, Prometheus metrics, and structured logging
- **Authentication**: Implemented JWT authentication with role-based access (viewer, editor, admin)
- **Rate Limiting**: Added Slowapi-based rate limiting
- **SSRF Prevention**: Created URL validator to block private IPs and non-HTTP schemes
- **Delta Ingestion**: Added content hashing (SHA-256) for reingestion detection
- **Health Endpoints**: Added `/health/ready` readiness check with dependency status
- **Production Deployment**: Added resource limits, restart policies, and health checks

### Changed

- **LLM Alignment**: Updated all agents (audit, correction, crawler) to use OpenAI-compatible endpoint (`http://spark-8013:4000/v1`) with `qwen3-coder-next` model
- **Dependencies**: Removed `langchain-anthropic` dependency (no longer used after LLM alignment)
- **Configuration**: Added LLM configuration section to `.env.example` with `RAG_LLM_ENDPOINT`, `RAG_LLM_MODEL`, `RAG_LLM_API_KEY` variables

### Fixed

- **A2A SDK Compatibility**: Updated to match a2a-sdk v0.3.26 API (snake_case field names, new enum values)
- **Markitdown API**: Switched from `convert_html()` to `convert_local()` with temporary file

---

## [Unreleased]

### Changed

- **LLM Alignment**: Updated crawler link discovery to use OpenAI-compatible endpoint (`http://spark-8013:4000/v1`) with `qwen3-coder-next` model, aligning with agent LLM configuration
- **Dependencies**: Removed `langchain-anthropic` dependency (no longer used after LLM alignment)
- **Configuration**: Added LLM configuration section to `.env.example` with `RAG_LLM_ENDPOINT`, `RAG_LLM_MODEL`, `RAG_LLM_API_KEY` variables

### Added

- Planning document for crawler LLM alignment (`ai-workspace/plans/crawler-llm-alignment.md`)
- Implementation summary report (`ai-workspace/summary-reports/llm-alignment-summary-2026-04-22.md`)

---

## Template for Future Entries

### Added
- Feature or capability description

### Changed
- Modification to existing functionality

### Removed
- Deprecated feature or capability

### Fixed
- Bug fix description

### Security
- Security-related changes
