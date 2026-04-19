# Phase 1, Subtask 4 — Docker Compose + Celery + CI/CD

> **Phase**: Phase 1 — Foundation
> **Subtask**: 4 of 5
> **Prerequisites**: Subtasks 1-3 must be complete (mono-repo, FastAPI backend, Next.js frontend all scaffolded)
> **Scope**: ~6 files to create, Docker Compose with 7 services, Celery app, GitHub Actions CI

---

## Context

This subtask creates the Docker Compose infrastructure (all 7 services), Dockerfiles for the API and web apps, the Celery worker skeleton, and the GitHub Actions CI pipeline. It combines Task 5 (Docker Compose), Task 6 (Celery app), and Task 7 (CI/CD) from the parent phase.

**Project Root**: `rag-pipeline/`

The mono-repo structure places infrastructure config at `rag-pipeline/infra/` and CI config at `rag-pipeline/.github/workflows/`.

---

## Relevant Technology Stack

| Component | Version | Notes |
|---|---|---|
| Docker | 27.x+ | Docker Desktop or Engine |
| Docker Compose | 2.x | Compose V2 |
| Postgres | 17 | Docker image `postgres:17` |
| Redis | 7.x | Docker image `redis:7-alpine` |
| Qdrant | 1.13+ | Docker image `qdrant/qdrant:latest` |
| Traefik | 3.x | Docker image `traefik:v3.4` |
| Python | 3.13.x | Docker image `python:3.13-slim` |
| Node.js | 22.x | Docker image `node:22-alpine` |
| Celery | 5.6.3 | Already in pyproject.toml from Subtask 2 |
| pnpm | 9.15.0 | For web build |

---

## Step-by-Step Implementation

### Step 1: Create `docker-compose.yml`

Create file `rag-pipeline/infra/docker-compose.yml`:

```yaml
services:
  # --- Reverse Proxy ---
  traefik:
    image: traefik:v3.4
    command:
      - "--api.insecure=true"
      - "--providers.docker=true"
      - "--providers.docker.exposedbydefault=false"
      - "--entrypoints.web.address=:80"
    ports:
      - "80:80"
      - "8080:8080" # Traefik dashboard
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    networks:
      - rag-network

  # --- FastAPI Backend ---
  api:
    build:
      context: ../apps/api
      dockerfile: Dockerfile
    environment:
      - RAG_DATABASE_URL=postgresql+asyncpg://rag_user:rag_pass@postgres:5432/rag_pipeline
      - RAG_REDIS_URL=redis://redis:6379/0
      - RAG_QDRANT_HOST=qdrant
      - RAG_CELERY_BROKER_URL=redis://redis:6379/1
      - RAG_CELERY_RESULT_BACKEND=redis://redis:6379/2
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.api.rule=PathPrefix(`/api`)"
      - "traefik.http.services.api.loadbalancer.server.port=8000"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      qdrant:
        condition: service_started
    volumes:
      - staging-data:/app/data/staging
    networks:
      - rag-network

  # --- Next.js Frontend ---
  web:
    build:
      context: ../apps/web
      dockerfile: Dockerfile
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost/api/v1
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.web.rule=PathPrefix(`/`)"
      - "traefik.http.routers.web.priority=1"
      - "traefik.http.services.web.loadbalancer.server.port=3000"
    networks:
      - rag-network

  # --- Celery Worker ---
  celery-worker:
    build:
      context: ../apps/api
      dockerfile: Dockerfile
    command: celery -A src.workers.celery_app worker --loglevel=info --concurrency=4
    environment:
      - RAG_DATABASE_URL=postgresql+asyncpg://rag_user:rag_pass@postgres:5432/rag_pipeline
      - RAG_REDIS_URL=redis://redis:6379/0
      - RAG_CELERY_BROKER_URL=redis://redis:6379/1
      - RAG_CELERY_RESULT_BACKEND=redis://redis:6379/2
    depends_on:
      - api
      - redis
    volumes:
      - staging-data:/app/data/staging
    networks:
      - rag-network

  # --- PostgreSQL ---
  postgres:
    image: postgres:17
    environment:
      POSTGRES_USER: rag_user
      POSTGRES_PASSWORD: rag_pass
      POSTGRES_DB: rag_pipeline
    ports:
      - "5432:5432"
    volumes:
      - postgres-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U rag_user -d rag_pipeline"]
      interval: 5s
      timeout: 5s
      retries: 5
    networks:
      - rag-network

  # --- Redis ---
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5
    networks:
      - rag-network

  # --- Qdrant ---
  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
      - "6334:6334" # gRPC
    volumes:
      - qdrant-data:/qdrant/storage
    environment:
      QDRANT__SERVICE__GRPC_PORT: 6334
    networks:
      - rag-network

volumes:
  postgres-data:
  redis-data:
  qdrant-data:
  staging-data:

networks:
  rag-network:
    driver: bridge
```

### Step 2: Create FastAPI Dockerfile

Create file `rag-pipeline/apps/api/Dockerfile`:

```dockerfile
FROM python:3.13-slim AS base

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]"

# Copy application code
COPY . .

# Create staging data directory
RUN mkdir -p /app/data/staging

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Step 3: Create Next.js Dockerfile

Create file `rag-pipeline/apps/web/Dockerfile`:

```dockerfile
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN corepack enable pnpm && pnpm install --frozen-lockfile

FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN corepack enable pnpm && pnpm build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

CMD ["node", "server.js"]
```

### Step 4: Update `next.config.js` for standalone output

Replace the contents of `rag-pipeline/apps/web/next.config.js` (or `next.config.ts` if generated):

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
};

module.exports = nextConfig;
```

### Step 5: Create `docker-compose.dev.yml` — development override

Create file `rag-pipeline/infra/docker-compose.dev.yml`:

```yaml
services:
  api:
    build:
      context: ../apps/api
    command: uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
    volumes:
      - ../apps/api/src:/app/src:cached
      - staging-data:/app/data/staging
    environment:
      - RAG_DATABASE_URL=postgresql+asyncpg://rag_user:rag_pass@postgres:5432/rag_pipeline

  web:
    build:
      context: ../apps/web
      dockerfile: Dockerfile
    command: pnpm dev
    volumes:
      - ../apps/web/src:/app/src:cached
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost/api/v1

  celery-worker:
    command: celery -A src.workers.celery_app worker --loglevel=debug --concurrency=2
    volumes:
      - ../apps/api/src:/app/src:cached
```

### Step 6: Create Celery app skeleton

Create file `rag-pipeline/apps/api/src/workers/celery_app.py`:

```python
"""Celery application configuration."""

from celery import Celery

from src.config import settings

celery_app = Celery(
    "rag_pipeline",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

# Auto-discover tasks in workers module
celery_app.autodiscover_tasks(["src.workers"])
```

### Step 7: Update `src/workers/__init__.py`

Replace the empty `rag-pipeline/apps/api/src/workers/__init__.py` with:

```python
"""Celery workers package."""

from src.workers.celery_app import celery_app

__all__ = ["celery_app"]
```

### Step 8: Create GitHub Actions CI pipeline

Create file `rag-pipeline/.github/workflows/ci.yml`:

```yaml
name: CI Pipeline

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint-and-test-api:
    name: "API: Lint, Type-Check, Test"
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: apps/api

    services:
      postgres:
        image: postgres:17
        env:
          POSTGRES_USER: rag_user
          POSTGRES_PASSWORD: rag_pass
          POSTGRES_DB: rag_pipeline
        ports:
          - 5432:5432
        options: >-
          --health-cmd "pg_isready -U rag_user -d rag_pipeline"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python 3.13
        uses: actions/setup-python@v5
        with:
          python-version: "3.13"

      - name: Install dependencies
        run: |
          pip install --upgrade pip
          pip install -e ".[dev]"

      - name: Lint with ruff
        run: ruff check src/ tests/

      - name: Type-check with mypy
        run: mypy src/

      - name: Run tests
        env:
          RAG_DATABASE_URL: postgresql+asyncpg://rag_user:rag_pass@localhost:5432/rag_pipeline
        run: pytest tests/ -v

  lint-and-test-web:
    name: "Web: Lint, Type-Check, Test"
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: apps/web

    steps:
      - uses: actions/checkout@v4

      - name: Setup pnpm
        uses: pnpm/action-setup@v4
        with:
          version: 9

      - name: Set up Node.js 22
        uses: actions/setup-node@v4
        with:
          node-version: "22"
          cache: "pnpm"
          cache-dependency-path: apps/web/pnpm-lock.yaml

      - name: Install dependencies
        run: pnpm install --frozen-lockfile

      - name: Lint
        run: pnpm lint

      - name: Type-check
        run: pnpm tsc --noEmit

      - name: Test
        run: pnpm vitest run

  docker-build:
    name: "Docker: Build Images"
    runs-on: ubuntu-latest
    needs: [lint-and-test-api, lint-and-test-web]
    steps:
      - uses: actions/checkout@v4

      - name: Build API image
        run: docker build -t rag-pipeline-api apps/api/

      - name: Build Web image
        run: docker build -t rag-pipeline-web apps/web/
```

---

## Files to Create/Modify

| # | File Path | Action |
|---|---|---|
| 1 | `infra/docker-compose.yml` | Create |
| 2 | `infra/docker-compose.dev.yml` | Create |
| 3 | `apps/api/Dockerfile` | Create |
| 4 | `apps/web/Dockerfile` | Create |
| 5 | `apps/web/next.config.js` | Modify (add standalone output) |
| 6 | `apps/api/src/workers/celery_app.py` | Create |
| 7 | `apps/api/src/workers/__init__.py` | Modify (replace empty) |
| 8 | `.github/workflows/ci.yml` | Create |

All paths relative to `rag-pipeline/`.

---

## Done-When Checklist

- [ ] `docker compose -f infra/docker-compose.yml up --build` starts all 7 services (traefik, api, web, celery-worker, postgres, redis, qdrant) without errors
- [ ] Postgres healthcheck passes — `pg_isready` returns success
- [ ] Redis is reachable — `redis-cli ping` returns `PONG`
- [ ] Qdrant dashboard is accessible at `http://localhost:6333/dashboard`
- [ ] Celery worker starts and connects to Redis broker
- [ ] `GET /api/v1/health` returns `200` via Traefik at `http://localhost/api/v1/health`
- [ ] Next.js dashboard loads at `http://localhost:3000` (or via Traefik at `http://localhost/`)
- [ ] CI pipeline YAML is committed at `.github/workflows/ci.yml`
- [ ] `apps/api/Dockerfile` builds successfully
- [ ] `apps/web/Dockerfile` builds successfully with standalone output

---

## Summary Report

Upon completion of this subtask, create a summary report at:
`rag-pipeline/ai-workspace/summary-reports/phase-1-subtask-4-docker-celery-cicd-summary.md`

The summary report must include:
- **Subtask**: Phase 1, Subtask 4 — Docker Compose + Celery + CI/CD
- **Status**: Complete / Partial / Blocked
- **Date**: {ISO 8601 date}
- **Files Created/Modified**: List every file path
- **Key Decisions**: Any deviations from the plan and why
- **Issues Encountered**: Problems and resolutions
- **Dependencies for Next Subtask**: What the next subtask needs to know
- **Verification Results**: Output of Done-When checklist items
