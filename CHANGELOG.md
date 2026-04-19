# Changelog

All notable changes to the RAG Pipeline project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

## [Unreleased] - Next Phases

### Phase 2: Crawl & Convert (Planned)
- URL fetching with HTTPX + Playwright
- Document conversion using MarkItDown
- Staging file browser UI

### Phase 3: Audit Agent (Planned)
- LangGraph Audit Agent with 10 validation rules
- Quality assessment and report generation

### Phase 4: Correction Agent (Planned)
- LangGraph Correction Agent
- A2A Protocol v1.0 implementation
- Iterative audit-correct loop

### Phase 5: Human Review (Planned)
- Review dashboard with Monaco editor
- Approval/rejection workflow

### Phase 6: Vector Ingestion (Planned)
- Markdown chunking with tiktoken
- FastEmbed vector embeddings
- Qdrant upsert pipeline

### Phase 7: MCP & Hardening (Planned)
- MCP server tools with 7 tools
- Observability stack (Prometheus, Grafana, Tempo, Loki)
- JWT authentication and rate limiting
- Production hardening

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
