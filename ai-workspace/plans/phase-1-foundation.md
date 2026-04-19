# Phase 1 — Foundation: Mono-Repo, Infrastructure & Core APIs

> **Prerequisites**: None — this is the first phase.
> **Ref**: [phase-0-index.md](phase-0-index.md) for pinned versions and target structure.

---

## Objective

Bootstrap the mono-repo with Turborepo, scaffold the FastAPI backend and Next.js frontend, stand up Docker Compose with all services, establish CI/CD, and create the initial Postgres schema.

---

## Task 1: Initialize Mono-Repo Root

**Working directory**: `rag-pipeline/`

### 1.1 Create the root `package.json`

```json
{
  "name": "rag-pipeline",
  "private": true,
  "packageManager": "pnpm@9.15.0",
  "scripts": {
    "dev": "turbo dev",
    "build": "turbo build",
    "lint": "turbo lint",
    "test": "turbo test",
    "type-check": "turbo type-check"
  },
  "devDependencies": {
    "turbo": "^2.0.0"
  }
}
```

### 1.2 Create `pnpm-workspace.yaml`

```yaml
packages:
  - "apps/*"
  - "packages/*"
```

### 1.3 Create `turbo.json`

```json
{
  "$schema": "https://turbo.build/schema.json",
  "globalDependencies": ["**/.env.*local"],
  "tasks": {
    "build": {
      "dependsOn": ["^build"],
      "outputs": [".next/**", "!.next/cache/**", "dist/**"]
    },
    "dev": {
      "cache": false,
      "persistent": true
    },
    "lint": {},
    "test": {},
    "type-check": {}
  }
}
```

### 1.4 Create `.gitignore`

```gitignore
node_modules/
.next/
dist/
.turbo/
__pycache__/
*.pyc
.venv/
*.egg-info/
.env
.env.local
.env.*.local
*.db
.DS_Store
```

### 1.5 Run initialization

```bash
pnpm install
```

**Done when**: `pnpm install` completes and `turbo.json` exists at repo root.

---

## Task 2: Scaffold FastAPI Backend

**Working directory**: `rag-pipeline/apps/api/`

### 2.1 Create `pyproject.toml`

```toml
[project]
name = "rag-pipeline-api"
version = "0.1.0"
description = "RAG Pipeline FastAPI Backend"
requires-python = ">=3.13"
dependencies = [
    "fastapi[standard]>=0.135.0",
    "uvicorn[standard]>=0.34.0",
    "sqlalchemy[asyncio]>=2.0.49",
    "alembic>=1.18.4",
    "asyncpg>=0.30.0",
    "pydantic>=2.13.0",
    "pydantic-settings>=2.8.0",
    "celery[redis]>=5.6.3",
    "redis>=6.2.0",
    "httpx>=0.28.0",
    "websockets>=15.0",
    "python-multipart>=0.0.20",
    "structlog>=25.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.25.0",
    "httpx>=0.28.0",
    "ruff>=0.11.0",
    "mypy>=1.15.0",
]

[tool.ruff]
target-version = "py313"
line-length = 120

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP", "B", "A", "SIM"]

[tool.mypy]
python_version = "3.13"
strict = true
plugins = ["pydantic.mypy"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

### 2.2 Create `src/main.py`

```python
"""RAG Pipeline API — main entry point."""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.routers import health


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Application lifespan handler — startup and shutdown."""
    # Startup: initialize DB connection pool, Redis, etc.
    yield
    # Shutdown: close connections


app = FastAPI(
    title="RAG Pipeline API",
    description="AI Knowledge Base RAG Ingestion Pipeline",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api/v1", tags=["health"])
```

### 2.3 Create `src/routers/__init__.py`

```python
```

### 2.4 Create `src/routers/health.py`

```python
"""Health check endpoint."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check() -> dict:
    """Return service health status."""
    return {
        "status": "healthy",
        "service": "rag-pipeline-api",
        "version": "0.1.0",
    }
```

### 2.5 Create `src/__init__.py`

```python
```

### 2.6 Create `src/config.py`

```python
"""Application configuration using pydantic-settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str = "postgresql+asyncpg://rag_user:rag_pass@postgres:5432/rag_pipeline"

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # Qdrant
    qdrant_host: str = "qdrant"
    qdrant_port: int = 6333

    # CORS
    cors_origins: list[str] = ["http://localhost:3000"]

    # Celery
    celery_broker_url: str = "redis://redis:6379/1"
    celery_result_backend: str = "redis://redis:6379/2"

    model_config = {"env_prefix": "RAG_", "env_file": ".env"}


settings = Settings()
```

### 2.7 Create `src/database.py`

```python
"""Async SQLAlchemy database engine and session factory."""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_size=20,
    max_overflow=10,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:  # type: ignore[misc]
    """FastAPI dependency that yields a database session."""
    async with async_session_factory() as session:
        yield session
```

### 2.8 Create empty module directories

Create these empty `__init__.py` files:

- `src/agents/__init__.py`
- `src/crawlers/__init__.py`
- `src/converters/__init__.py`
- `src/embeddings/__init__.py`
- `src/ingest/__init__.py`
- `src/mcp/__init__.py`
- `src/models/__init__.py`
- `src/schemas/__init__.py`
- `src/workers/__init__.py`
- `tests/__init__.py`

Each file should contain only:
```python
```

**Done when**: `python -m uvicorn src.main:app --host 0.0.0.0 --port 8000` starts without errors.

---

## Task 3: Create SQLAlchemy Models & Alembic Migrations

**Working directory**: `rag-pipeline/apps/api/`

### 3.1 Create `src/models/base.py`

```python
"""SQLAlchemy declarative base with common columns."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


class TimestampMixin:
    """Mixin that adds created_at and updated_at columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class UUIDMixin:
    """Mixin that adds a UUID primary key."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
```

### 3.2 Create `src/models/ingestion_job.py`

```python
"""IngestionJob model — tracks a URL ingestion job through the pipeline."""

import uuid
from enum import StrEnum

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDMixin


class JobStatus(StrEnum):
    """Possible states for an ingestion job."""

    PENDING = "pending"
    CRAWLING = "crawling"
    CONVERTING = "converting"
    AUDITING = "auditing"
    CORRECTING = "correcting"
    REVIEW = "review"
    APPROVED = "approved"
    GENERATING_JSON = "generating_json"
    EMBEDDING = "embedding"
    INGESTED = "ingested"
    FAILED = "failed"


class IngestionJob(Base, UUIDMixin, TimestampMixin):
    """Represents a single URL ingestion job."""

    __tablename__ = "ingestion_jobs"

    url: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), default=JobStatus.PENDING, nullable=False
    )
    crawl_all_docs: Mapped[bool] = mapped_column(default=False)
    total_documents: Mapped[int] = mapped_column(default=0)
    processed_documents: Mapped[int] = mapped_column(default=0)
    current_audit_round: Mapped[int] = mapped_column(default=0)

    # Relationships
    documents: Mapped[list["Document"]] = relationship(back_populates="job")
    audit_reports: Mapped[list["AuditReport"]] = relationship(back_populates="job")
    vector_collections: Mapped[list["VectorCollection"]] = relationship(back_populates="job")
```

### 3.3 Create `src/models/document.py`

```python
"""Document model — a single page fetched and converted to Markdown."""

import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDMixin


class Document(Base, UUIDMixin, TimestampMixin):
    """A single documentation page within an ingestion job."""

    __tablename__ = "documents"

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ingestion_jobs.id"), nullable=False
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(String(255))
    raw_html_path: Mapped[str | None] = mapped_column(Text)
    markdown_path: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    word_count: Mapped[int | None] = mapped_column(Integer)
    quality_score: Mapped[int | None] = mapped_column(Integer)

    # Relationships
    job: Mapped["IngestionJob"] = relationship(back_populates="documents")
```

### 3.4 Create `src/models/audit_report.py`

```python
"""AuditReport model — results from an Audit Agent round."""

import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDMixin


class AuditReport(Base, UUIDMixin, TimestampMixin):
    """Stores audit results for one round of document validation."""

    __tablename__ = "audit_reports"

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ingestion_jobs.id"), nullable=False
    )
    round: Mapped[int] = mapped_column(Integer, nullable=False)
    total_issues: Mapped[int] = mapped_column(Integer, default=0)
    issues_json: Mapped[dict | None] = mapped_column(JSON)
    summary: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(30), default="issues_found", nullable=False
    )
    agent_notes: Mapped[str | None] = mapped_column(Text)

    # Relationships
    job: Mapped["IngestionJob"] = relationship(back_populates="audit_reports")
```

### 3.5 Create `src/models/vector_collection.py`

```python
"""VectorCollection model — tracks Qdrant collections created by the pipeline."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDMixin


class VectorCollection(Base, UUIDMixin, TimestampMixin):
    """Tracks a Qdrant collection created from an ingestion job."""

    __tablename__ = "vector_collections"

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ingestion_jobs.id"), nullable=False
    )
    qdrant_collection_name: Mapped[str] = mapped_column(String(255), nullable=False)
    document_count: Mapped[int] = mapped_column(Integer, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    vector_dimensions: Mapped[int] = mapped_column(Integer, default=3072)
    embedded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    job: Mapped["IngestionJob"] = relationship(back_populates="vector_collections")
```

### 3.6 Update `src/models/__init__.py` to import all models

```python
"""SQLAlchemy models package."""

from src.models.audit_report import AuditReport
from src.models.base import Base
from src.models.document import Document
from src.models.ingestion_job import IngestionJob, JobStatus
from src.models.vector_collection import VectorCollection

__all__ = [
    "Base",
    "AuditReport",
    "Document",
    "IngestionJob",
    "JobStatus",
    "VectorCollection",
]
```

### 3.7 Initialize Alembic

```bash
cd apps/api
alembic init alembic
```

### 3.8 Edit `alembic.ini` — set sqlalchemy.url

Replace the `sqlalchemy.url` line:
```ini
sqlalchemy.url = postgresql+asyncpg://rag_user:rag_pass@localhost:5432/rag_pipeline
```

### 3.9 Edit `alembic/env.py`

Replace the entire contents with:

```python
"""Alembic environment configuration for async SQLAlchemy."""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from src.config import settings
from src.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in offline mode."""
    url = settings.database_url
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    """Run migrations using provided connection."""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in async online mode."""
    connectable = create_async_engine(settings.database_url)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in online mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

### 3.10 Generate initial migration

```bash
alembic revision --autogenerate -m "initial schema"
```

### 3.11 Apply migration

```bash
alembic upgrade head
```

**Done when**: `alembic upgrade head` creates all 4 tables in Postgres without errors.

---

## Task 4: Scaffold Next.js Frontend

**Working directory**: `rag-pipeline/apps/web/`

### 4.1 Create Next.js app

```bash
cd rag-pipeline/apps
npx create-next-app@latest web \
  --typescript \
  --tailwind \
  --eslint \
  --app \
  --src-dir \
  --import-alias "@/*" \
  --use-pnpm
```

### 4.2 Install additional dependencies

```bash
cd web
pnpm add @reduxjs/toolkit react-redux
pnpm add -D vitest @testing-library/react @testing-library/jest-dom
```

### 4.3 Initialize shadcn/ui

```bash
npx shadcn@latest init
```

When prompted:
- Style: **New York**
- Base color: **Neutral**
- CSS variables: **Yes**

### 4.4 Add initial shadcn components

```bash
npx shadcn@latest add button card input badge tabs separator
```

### 4.5 Create Redux store — `src/store/store.ts`

```typescript
import { configureStore } from "@reduxjs/toolkit";
import { setupListeners } from "@reduxjs/toolkit/query";
import { apiSlice } from "./api/api-slice";

export const store = configureStore({
  reducer: {
    [apiSlice.reducerPath]: apiSlice.reducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware().concat(apiSlice.middleware),
});

setupListeners(store.dispatch);

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
```

### 4.6 Create RTK Query base API — `src/store/api/api-slice.ts`

```typescript
import { createApi, fetchBaseQuery } from "@reduxjs/toolkit/query/react";

export const apiSlice = createApi({
  reducerPath: "api",
  baseQuery: fetchBaseQuery({
    baseUrl: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1",
  }),
  tagTypes: ["Jobs", "Documents", "AuditReports"],
  endpoints: () => ({}),
});
```

### 4.7 Create Redux hooks — `src/store/hooks.ts`

```typescript
import { useDispatch, useSelector } from "react-redux";
import type { AppDispatch, RootState } from "./store";

export const useAppDispatch = useDispatch.withTypes<AppDispatch>();
export const useAppSelector = useSelector.withTypes<RootState>();
```

### 4.8 Create store provider — `src/store/provider.tsx`

```tsx
"use client";

import { Provider } from "react-redux";
import { store } from "./store";

export function StoreProvider({ children }: { children: React.ReactNode }) {
  return <Provider store={store}>{children}</Provider>;
}
```

### 4.9 Update `src/app/layout.tsx`

```tsx
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { StoreProvider } from "@/store/provider";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "RAG Pipeline Dashboard",
  description: "AI Knowledge Base RAG Ingestion Pipeline",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <StoreProvider>{children}</StoreProvider>
      </body>
    </html>
  );
}
```

### 4.10 Create placeholder home page — `src/app/page.tsx`

```tsx
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function HomePage() {
  return (
    <main className="container mx-auto p-8">
      <h1 className="text-3xl font-bold mb-8">RAG Pipeline Dashboard</h1>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Ingestion Jobs</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-muted-foreground">No jobs yet. Submit a URL to get started.</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Documents</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-muted-foreground">Documents will appear after crawling.</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Vector Collections</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-muted-foreground">Collections will appear after ingestion.</p>
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
```

### 4.11 Create `.env.local`

```env
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

**Done when**: `pnpm dev` starts Next.js at `http://localhost:3000` and displays the dashboard placeholder.

---

## Task 5: Docker Compose Configuration

**Working directory**: `rag-pipeline/infra/`

### 5.1 Create `docker-compose.yml`

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

### 5.2 Create FastAPI Dockerfile — `apps/api/Dockerfile`

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

### 5.3 Create Next.js Dockerfile — `apps/web/Dockerfile`

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

### 5.4 Update `apps/web/next.config.js` for standalone output

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
};

module.exports = nextConfig;
```

### 5.5 Create `docker-compose.dev.yml` — development override

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

**Done when**: `docker compose -f docker-compose.yml up --build` starts all 7 services (traefik, api, web, celery-worker, postgres, redis, qdrant) without errors.

---

## Task 6: Create Celery App Skeleton

**Working directory**: `rag-pipeline/apps/api/`

### 6.1 Create `src/workers/celery_app.py`

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

### 6.2 Update `src/workers/__init__.py`

```python
"""Celery workers package."""

from src.workers.celery_app import celery_app

__all__ = ["celery_app"]
```

**Done when**: Celery worker starts and connects to Redis broker without errors.

---

## Task 7: CI/CD Pipeline

**Working directory**: `rag-pipeline/`

### 7.1 Create `.github/workflows/ci.yml`

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

**Done when**: CI config is committed and a push to main triggers the pipeline.

---

## Task 8: Create Shared Pydantic Schemas

**Working directory**: `rag-pipeline/apps/api/`

### 8.1 Create `src/schemas/job.py`

```python
"""Pydantic schemas for ingestion jobs."""

import uuid
from datetime import datetime

from pydantic import BaseModel, HttpUrl


class JobCreate(BaseModel):
    """Schema for creating a new ingestion job."""

    url: HttpUrl
    crawl_all_docs: bool = False


class JobResponse(BaseModel):
    """Schema for job API responses."""

    id: uuid.UUID
    url: str
    status: str
    crawl_all_docs: bool
    total_documents: int
    processed_documents: int
    current_audit_round: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JobStatusResponse(BaseModel):
    """Lightweight job status for polling."""

    id: uuid.UUID
    status: str
    total_documents: int
    processed_documents: int
    current_audit_round: int
```

### 8.2 Create `src/schemas/document.py`

```python
"""Pydantic schemas for documents."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class DocumentResponse(BaseModel):
    """Schema for document API responses."""

    id: uuid.UUID
    job_id: uuid.UUID
    url: str
    title: str | None
    status: str
    word_count: int | None
    quality_score: int | None
    created_at: datetime

    model_config = {"from_attributes": True}
```

### 8.3 Update `src/schemas/__init__.py`

```python
"""Pydantic schemas package."""

from src.schemas.document import DocumentResponse
from src.schemas.job import JobCreate, JobResponse, JobStatusResponse

__all__ = [
    "DocumentResponse",
    "JobCreate",
    "JobResponse",
    "JobStatusResponse",
]
```

**Done when**: Schemas import cleanly — `python -c "from src.schemas import JobCreate, JobResponse"` succeeds.

---

## Task 9: Write Initial Tests

**Working directory**: `rag-pipeline/apps/api/`

### 9.1 Create `tests/conftest.py`

```python
"""Shared test fixtures."""

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app


@pytest.fixture
async def client():
    """Async HTTP test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
```

### 9.2 Create `tests/test_health.py`

```python
"""Health endpoint tests."""

import pytest


@pytest.mark.asyncio
async def test_health_endpoint(client):
    """GET /api/v1/health should return 200 with service info."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "rag-pipeline-api"
    assert "version" in data
```

**Done when**: `pytest tests/ -v` passes with 1 test green.

---

## Phase 1 Done-When Checklist

- [ ] `pnpm install` at repo root completes successfully
- [ ] `docker compose -f infra/docker-compose.yml up --build` starts all 7 services with no errors
- [ ] `GET /api/v1/health` returns `200` with `{"status": "healthy"}`
- [ ] Next.js dashboard loads at `http://localhost:3000` showing 3 placeholder cards
- [ ] Postgres migrations run cleanly via `alembic upgrade head` — 4 tables created
- [ ] Redis is reachable — `redis-cli ping` returns `PONG`
- [ ] Qdrant dashboard is accessible at `http://localhost:6333/dashboard`
- [ ] Celery worker starts and connects to Redis broker
- [ ] `pytest tests/ -v` passes with ≥1 test
- [ ] CI pipeline YAML is committed at `.github/workflows/ci.yml`
- [ ] All code passes `ruff check` and `mypy` without errors
