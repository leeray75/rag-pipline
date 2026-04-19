# Phase 1, Subtask 2 — FastAPI Backend Scaffold + Database Models & Migrations

> **Phase**: Phase 1 — Foundation
> **Subtask**: 2 of 5
> **Prerequisites**: Subtask 1 (Mono-Repo Initialization) must be complete
> **Scope**: ~25 files to create, Alembic init + migration

---

## Context

This subtask scaffolds the FastAPI backend application at `apps/api/`, creates all SQLAlchemy models with Alembic migrations, and sets up the database connection layer. It combines Task 2 (FastAPI scaffold) and Task 3 (SQLAlchemy models & Alembic) from the parent phase.

**Project Root**: `rag-pipeline/`
**Working Directory**: `rag-pipeline/apps/api/`

---

## Relevant Technology Stack

| Package | Version | Install |
|---|---|---|
| Python | 3.13.x | Runtime |
| FastAPI | 0.135.3 | `pip install "fastapi[standard]"` |
| Pydantic | 2.13.0 | `pip install pydantic` |
| pydantic-settings | 2.8.0 | `pip install pydantic-settings` |
| SQLAlchemy | 2.0.49 | `pip install "sqlalchemy[asyncio]"` |
| Alembic | 1.18.4 | `pip install alembic` |
| asyncpg | 0.30.0 | `pip install asyncpg` |
| Celery | 5.6.3 | `pip install "celery[redis]"` |
| Redis (py) | 6.2.0 | `pip install redis` |
| uvicorn | 0.34.0 | `pip install "uvicorn[standard]"` |
| httpx | 0.28.0 | `pip install httpx` |
| structlog | 25.4.0 | `pip install structlog` |
| Postgres | 17 | Docker image `postgres:17` |

---

## Step-by-Step Implementation

### Step 1: Create `pyproject.toml`

Create file `rag-pipeline/apps/api/pyproject.toml`:

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

### Step 2: Create `src/main.py`

Create file `rag-pipeline/apps/api/src/main.py`:

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

### Step 3: Create `src/__init__.py`

Create empty file `rag-pipeline/apps/api/src/__init__.py`:

```python
```

### Step 4: Create `src/routers/__init__.py`

Create empty file `rag-pipeline/apps/api/src/routers/__init__.py`:

```python
```

### Step 5: Create `src/routers/health.py`

Create file `rag-pipeline/apps/api/src/routers/health.py`:

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

### Step 6: Create `src/config.py`

Create file `rag-pipeline/apps/api/src/config.py`:

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

### Step 7: Create `src/database.py`

Create file `rag-pipeline/apps/api/src/database.py`:

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

### Step 8: Create empty module `__init__.py` stubs

Create the following empty `__init__.py` files (each containing no code):

- `rag-pipeline/apps/api/src/agents/__init__.py`
- `rag-pipeline/apps/api/src/crawlers/__init__.py`
- `rag-pipeline/apps/api/src/converters/__init__.py`
- `rag-pipeline/apps/api/src/embeddings/__init__.py`
- `rag-pipeline/apps/api/src/ingest/__init__.py`
- `rag-pipeline/apps/api/src/mcp/__init__.py`
- `rag-pipeline/apps/api/src/models/__init__.py` (will be updated in Step 14)
- `rag-pipeline/apps/api/src/schemas/__init__.py`
- `rag-pipeline/apps/api/src/workers/__init__.py`
- `rag-pipeline/apps/api/tests/__init__.py`

### Step 9: Create `src/models/base.py`

Create file `rag-pipeline/apps/api/src/models/base.py`:

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

### Step 10: Create `src/models/ingestion_job.py`

Create file `rag-pipeline/apps/api/src/models/ingestion_job.py`:

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

### Step 11: Create `src/models/document.py`

Create file `rag-pipeline/apps/api/src/models/document.py`:

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

### Step 12: Create `src/models/audit_report.py`

Create file `rag-pipeline/apps/api/src/models/audit_report.py`:

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

### Step 13: Create `src/models/vector_collection.py`

Create file `rag-pipeline/apps/api/src/models/vector_collection.py`:

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

### Step 14: Update `src/models/__init__.py` to import all models

Replace the empty file with:

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

### Step 15: Initialize Alembic

```bash
cd rag-pipeline/apps/api
alembic init alembic
```

### Step 16: Edit `alembic.ini` — set sqlalchemy.url

In the generated `alembic.ini`, replace the `sqlalchemy.url` line:

```ini
sqlalchemy.url = postgresql+asyncpg://rag_user:rag_pass@localhost:5432/rag_pipeline
```

### Step 17: Replace `alembic/env.py`

Replace the entire contents of `rag-pipeline/apps/api/alembic/env.py` with:

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

### Step 18: Generate and apply initial migration

```bash
cd rag-pipeline/apps/api
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

**Note**: Postgres must be running (via Docker) for migration to apply. If Postgres is not yet available, the migration file can be generated offline and applied in Subtask 4 after Docker Compose is up.

---

## Files to Create/Modify

| # | File Path | Action |
|---|---|---|
| 1 | `apps/api/pyproject.toml` | Create |
| 2 | `apps/api/src/__init__.py` | Create |
| 3 | `apps/api/src/main.py` | Create |
| 4 | `apps/api/src/config.py` | Create |
| 5 | `apps/api/src/database.py` | Create |
| 6 | `apps/api/src/routers/__init__.py` | Create |
| 7 | `apps/api/src/routers/health.py` | Create |
| 8 | `apps/api/src/models/__init__.py` | Create |
| 9 | `apps/api/src/models/base.py` | Create |
| 10 | `apps/api/src/models/ingestion_job.py` | Create |
| 11 | `apps/api/src/models/document.py` | Create |
| 12 | `apps/api/src/models/audit_report.py` | Create |
| 13 | `apps/api/src/models/vector_collection.py` | Create |
| 14 | `apps/api/src/agents/__init__.py` | Create (empty) |
| 15 | `apps/api/src/crawlers/__init__.py` | Create (empty) |
| 16 | `apps/api/src/converters/__init__.py` | Create (empty) |
| 17 | `apps/api/src/embeddings/__init__.py` | Create (empty) |
| 18 | `apps/api/src/ingest/__init__.py` | Create (empty) |
| 19 | `apps/api/src/mcp/__init__.py` | Create (empty) |
| 20 | `apps/api/src/schemas/__init__.py` | Create (empty) |
| 21 | `apps/api/src/workers/__init__.py` | Create (empty) |
| 22 | `apps/api/tests/__init__.py` | Create (empty) |
| 23 | `apps/api/alembic.ini` | Create (via alembic init, then edit) |
| 24 | `apps/api/alembic/env.py` | Create (replace generated) |
| 25 | `apps/api/alembic/versions/*.py` | Create (via autogenerate) |

All paths relative to `rag-pipeline/`.

---

## Done-When Checklist

- [ ] `pyproject.toml` exists at `apps/api/pyproject.toml` with all dependencies listed
- [ ] `python -m uvicorn src.main:app --host 0.0.0.0 --port 8000` starts without errors (from `apps/api/`)
- [ ] `GET /api/v1/health` returns `200` with `{"status": "healthy"}`
- [ ] All 10 empty `__init__.py` module stubs exist
- [ ] All 4 SQLAlchemy models import cleanly: `from src.models import Base, IngestionJob, Document, AuditReport, VectorCollection, JobStatus`
- [ ] Alembic is initialized with async `env.py`
- [ ] `alembic revision --autogenerate -m "initial schema"` generates a migration file
- [ ] `alembic upgrade head` creates all 4 tables (ingestion_jobs, documents, audit_reports, vector_collections) — requires Postgres

---

## Summary Report

Upon completion of this subtask, create a summary report at:
`rag-pipeline/ai-workspace/summary-reports/phase-1-subtask-2-fastapi-and-database-summary.md`

The summary report must include:
- **Subtask**: Phase 1, Subtask 2 — FastAPI Backend Scaffold + Database Models & Migrations
- **Status**: Complete / Partial / Blocked
- **Date**: {ISO 8601 date}
- **Files Created/Modified**: List every file path
- **Key Decisions**: Any deviations from the plan and why
- **Issues Encountered**: Problems and resolutions
- **Dependencies for Next Subtask**: What the next subtask needs to know
- **Verification Results**: Output of Done-When checklist items
