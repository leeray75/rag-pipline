# Getting Started Guide

Step-by-step guide to get the RAG Pipeline up and running.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Development Setup](#development-setup)
- [Running in Production](#running-in-production)
- [First Ingestion](#first-ingestion)
- [Common Tasks](#common-tasks)

---

## Prerequisites

### Required Software

| Software | Version | Notes |
|----------|---------|-------|
| Docker | 27.x+ | Docker Desktop or Engine |
| Docker Compose | 2.x+ | Compose V2 required |
| Traefik | 3.6.13 | Reverse proxy (port 80) |
| Node.js | 22+ | Including npm |
| pnpm | 9+ | Package manager |
| Python | 3.13+ | Runtime and development |

### Verify Installations

```bash
# Docker
docker --version
docker compose version

# Node.js and pnpm
node --version
pnpm --version

# Python
python --version
pip --version
```

---

## Quick Start

### 1. Clone and Install

```bash
# Clone the repository
git clone <repo-url>
cd rag-pipeline

# Install monorepo dependencies
pnpm install

# Install API dependencies
cd apps/api
pip install -e ".[dev]"
playwright install chromium
cd ../..
```

### 2. Start Infrastructure

```bash
cd infra
docker compose up -d
cd ..
```

### 3. Run Database Migrations

```bash
cd apps/api
alembic upgrade head
cd ..
```

### 4. Start Development Servers

```bash
pnpm dev
```

### 5. Access the Application

| Service | URL |
|---------|-----|
| Frontend | http://localhost/ (Traefik) |
| API | http://localhost/api/v1 (Traefik) |
| API Docs | http://localhost/api/docs (Traefik) |
| Traefik Dashboard | http://localhost:8080 |

---

## Development Setup

### Directory Structure

```
rag-pipeline/
├── apps/
│   ├── api/              # FastAPI backend (Python)
│   │   ├── src/
│   │   │   ├── agents/   # LangGraph agents
│   │   │   ├── auth/     # Authentication
│   │   │   ├── crawlers/ # URL fetching
│   │   │   ├── converters/ # HTML to Markdown
│   │   │   ├── embeddings/ # FastEmbed models
│   │   │   ├── ingest/   # Chunking & embedding
│   │   │   ├── mcp/      # MCP server
│   │   │   ├── models/   # SQLAlchemy models
│   │   │   ├── routers/  # API routes
│   │   │   ├── schemas/  # Pydantic schemas
│   │   │   ├── security/ # SSRF prevention
│   │   │   ├── workers/  # Celery tasks
│   │   │   └── main.py
│   │   ├── tests/
│   │   ├── alembic/
│   │   ├── Dockerfile
│   │   └── pyproject.toml
│   └── web/              # Next.js frontend
│       ├── src/
│       │   ├── app/      # App Router pages
│       │   ├── components/ # UI components
│       │   ├── features/   # Feature modules
│       │   ├── store/      # Redux store
│       │   └── lib/        # Utilities
│       ├── Dockerfile
│       └── package.json
├── infra/
│   ├── docker-compose.yml
│   ├── docker-compose.dev.yml
│   ├── docker-compose.prod.yml
│   └── traefik-config.yml
├── docs/                 # This documentation
├── ai-workspace/         # Planning & reports
├── package.json
├── pnpm-workspace.yaml
└── turbo.json
```

### Environment Variables

**API (apps/api/.env)**

```env
# Database
RAG_DATABASE_URL=postgresql+asyncpg://rag_user:rag_pass@postgres:5432/rag_pipeline

# Redis
RAG_REDIS_URL=redis://redis:6379/0

# Qdrant
QDRANT_URL=http://qdrant:6333

# LLM (OpenAI-compatible endpoint)
LLM_ENDPOINT=http://spark-8013:4000/v1
LLM_API_KEY=not-needed

# JWT Authentication
JWT_SECRET=CHANGE-ME-IN-PRODUCTION
JWT_EXPIRY_HOURS=24

# Rate Limiting
RATE_LIMIT=100/minute

# Logging
LOG_FORMAT=console
LOG_LEVEL=INFO

# Embedding
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
EMBEDDING_BATCH_SIZE=100
```

**Frontend (.env.local)**

```env
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

### Running Services Individually

**API (FastAPI)**

```bash
cd apps/api
uvicorn src.main:app --reload
```

**Frontend (Next.js)**

```bash
cd apps/web
pnpm dev
```

**Celery Worker**

```bash
cd apps/api
celery -A src.workers.celery_app worker --loglevel=info --concurrency=4
```

---

## Running in Production

### Production Configuration

```bash
# Validate merged configuration
docker compose -f docker-compose.yml -f infra/docker-compose.prod.yml config

# Start production stack
docker compose -f docker-compose.yml -f infra/docker-compose.prod.yml up -d

# Run migrations
docker compose exec api alembic upgrade head

# Check service status
docker compose ps
```

### Production Environment Variables

```env
# Production settings
ENVIRONMENT=production
LOG_FORMAT=json
OTEL_ENABLED=true

# JWT
JWT_SECRET=<generate-with-secrets>

# Rate Limiting
RATE_LIMIT=1000/minute
```

### Viewing Logs

```bash
# API logs
docker compose logs -f api

# Celery logs
docker compose logs -f celery-worker

# PostgreSQL logs
docker compose logs -f postgres

# Traefik logs
docker compose logs -f traefik
```

---

## First Ingestion

### Via API

```bash
# 1. Create an ingestion job
curl -X POST http://localhost:8000/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com/docs",
    "crawl_all_docs": true
  }'

# 2. Trigger the audit workflow
curl -X POST http://localhost:8000/api/v1/jobs/{job_id}/audit

# 3. Trigger chunking and embedding
curl -X POST http://localhost:8000/api/v1/ingest/jobs/{job_id}/chunk
curl -X POST http://localhost:8000/api/v1/ingest/jobs/{job_id}/embed \
  -H "Content-Type: application/json" \
  -d '{"collection_name": "my-docs"}'
```

### Via Frontend

1. Navigate to http://localhost:3000
2. Enter a URL in the ingestion form
3. Click "Start Crawl"
4. Monitor progress in real-time
5. Review documents in the staging browser
6. Trigger audit workflow
7. Review and approve documents

---

## Common Tasks

### Restart Services

```bash
# Restart all services
docker compose restart

# Restart specific service
docker compose restart api
docker compose restart web
docker compose restart celery-worker
```

### View Service Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f api
```

### Run Database Migration

```bash
cd apps/api

# View migration history
alembic history

# Create new migration
alembic revision -m "description"

# Run migrations
alembic upgrade head

# Downgrade
alembic downgrade -1
```

### Check Qdrant Collection

```bash
# List collections
curl http://localhost:6333/collections

# Get collection info
curl http://localhost:6333/collections/my-docs
```

### Clear Data

```bash
# Stop services
docker compose down

# Remove volumes (WARNING: deletes all data)
docker compose down -v

# Start fresh
docker compose up -d
```

### Docker Compose Commands (Quick Reference)

Common docker compose operations for managing the RAG Pipeline infrastructure:

```bash
# Build all services
docker compose -f ./infra/docker-compose.yml build

# Start all services in detached mode
docker compose -f ./infra/docker-compose.yml up -d

# View running services
docker compose ps

# Stop all services
docker compose -f ./infra/docker-compose.yml down

# Stop and remove volumes (WARNING: deletes all data)
docker compose -f ./infra/docker-compose.yml down -v

# View logs for all services
docker compose logs -f

# View logs for a specific service
docker compose logs -f api
docker compose logs -f web
docker compose logs -f postgres
docker compose logs -f redis
docker compose logs -f qdrant
docker compose logs -f traefik

# Execute commands inside running containers
docker compose exec api bash
docker compose exec web bash
docker compose exec postgres psql -U postgres -d rag_pipeline
docker compose exec qdrant curl http://localhost:6333/readyz

# Validate docker-compose configuration
docker compose config

# Restart specific services
docker compose restart api
docker compose restart web
docker compose restart postgres
docker compose restart redis
docker compose restart qdrant

# Rebuild and restart
docker compose build --no-cache
docker compose up -d
```

### Run Tests

```bash
# API tests
cd apps/api
pytest tests/ -v

# Web tests
cd apps/web
pnpm test
```

---

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker compose logs <service>

# Check resource limits
docker compose ps

# Validate configuration
docker compose config
```

### Database Connection Issues

```bash
# Check PostgreSQL is running
docker compose ps postgres

# Verify connection
docker compose exec postgres pg_isready -U rag_user
```

### Frontend Can't Connect to API

```bash
# Check API is running
docker compose ps api

# Check CORS is enabled in API config
docker compose exec api cat /app/src/config.py
```

### Embedding Fails

```bash
# Check Qdrant is running
docker compose ps qdrant

# Check embedding service logs
docker compose logs api | grep -i embedding
```

---

## Next Steps

- Read the [Architecture Documentation](./architecture.md) to understand system design
- Check the [API Reference](./api-reference.md) for detailed endpoint documentation
- Review the [Operations Runbook](./runbook.md) for common issues and solutions
- Explore the [Lessons Learned](../ai-workspace/docs/lessons-learned.md) for anti-patterns

---

*Last updated: 2026-04-23*
