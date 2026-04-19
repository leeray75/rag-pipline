# SQLAlchemy 2.0 Async + Alembic — RAG Reference Document

<!-- RAG_METADATA
topic: database, orm, migrations, async
library: sqlalchemy, alembic
version: sqlalchemy 2.0.49, alembic 1.18.4
python_min: 3.9
tags: sqlalchemy, async, asyncio, alembic, migrations, postgresql, mapped-column, content-hash
use_case: phase-7-subtask-4-production-hardening
-->

## Overview

**SQLAlchemy 2.0** introduces a fully async ORM with `AsyncSession` and `AsyncEngine`. **Alembic 1.18.x** handles schema migrations with `--autogenerate` support for SQLAlchemy 2.0 mapped models.

**Install**:
```bash
pip install sqlalchemy[asyncio] alembic asyncpg
```

---

## SQLAlchemy 2.0 Model Definition (Declarative with `Mapped`)

```python
from datetime import datetime, timezone
from sqlalchemy import String, Text, DateTime, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Phase 7 addition — SHA-256 hash for delta detection
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    
    status: Mapped[str] = mapped_column(String(32), default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationship
    chunks: Mapped[list["ChunkRecord"]] = relationship(
        "ChunkRecord", back_populates="document", cascade="all, delete-orphan"
    )
```

**Key SQLAlchemy 2.0 patterns**:
- `Mapped[T]` — type-annotated column declaration (replaces `Column(...)`)
- `mapped_column(...)` — column configuration
- `Mapped[str | None]` — nullable column
- `Mapped[str]` — non-nullable column

---

## Async Engine and Session Setup

```python
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

DATABASE_URL = "postgresql+asyncpg://user:password@localhost:5432/rag_pipeline"

engine = create_async_engine(
    DATABASE_URL,
    echo=False,           # Set True for SQL query logging
    pool_size=10,         # Connection pool size
    max_overflow=20,      # Extra connections beyond pool_size
    pool_pre_ping=True,   # Verify connections before use
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,   # Don't expire objects after commit
)


async def get_db():
    """FastAPI dependency — yields an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

---

## Async CRUD Operations

### SELECT (Query)

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Select all documents for a job
async def get_documents_by_job(job_id: str, db: AsyncSession) -> list[Document]:
    stmt = select(Document).where(Document.job_id == job_id)
    result = await db.execute(stmt)
    return result.scalars().all()

# Select single document by URL
async def get_document_by_url(source_url: str, db: AsyncSession) -> Document | None:
    stmt = select(Document).where(Document.source_url == source_url)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()

# Select with multiple conditions
async def get_changed_documents(job_id: str, db: AsyncSession) -> list[Document]:
    stmt = (
        select(Document)
        .where(Document.job_id == job_id)
        .where(Document.status == "pending")
        .order_by(Document.created_at.desc())
    )
    result = await db.execute(stmt)
    return result.scalars().all()
```

### INSERT

```python
async def create_document(data: dict, db: AsyncSession) -> Document:
    doc = Document(**data)
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc
```

### UPDATE

```python
from sqlalchemy import update

async def update_content_hash(doc_id: str, content_hash: str, db: AsyncSession) -> None:
    stmt = (
        update(Document)
        .where(Document.id == doc_id)
        .values(content_hash=content_hash)
    )
    await db.execute(stmt)
    await db.commit()
```

### DELETE

```python
from sqlalchemy import delete

async def delete_chunks_for_documents(document_ids: list[str], db: AsyncSession) -> int:
    stmt = delete(ChunkRecord).where(ChunkRecord.document_id.in_(document_ids))
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount
```

---

## Content Hash Pattern (Delta Detection)

```python
import hashlib

def compute_content_hash(content: str) -> str:
    """SHA-256 hash of document content for change detection."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()

async def detect_document_changes(
    job_id: str,
    new_documents: list[dict],
    db: AsyncSession,
) -> dict:
    """Compare new content hashes against stored hashes."""
    stmt = select(Document).where(Document.job_id == job_id)
    result = await db.execute(stmt)
    existing = {d.source_url: d for d in result.scalars().all()}

    added, updated, unchanged, removed = [], [], [], []
    new_urls = {d["source_url"] for d in new_documents}
    removed = list(set(existing.keys()) - new_urls)

    for doc_data in new_documents:
        url = doc_data["source_url"]
        new_hash = compute_content_hash(doc_data["content"])
        if url not in existing:
            added.append(url)
        elif existing[url].content_hash != new_hash:
            updated.append(url)
        else:
            unchanged.append(url)

    return {"added": added, "updated": updated, "unchanged": unchanged, "removed": removed}
```

---

## Alembic Setup

### Initialize Alembic

```bash
cd rag-pipeline/apps/api
alembic init alembic
```

### Configure `alembic.ini`

```ini
[alembic]
script_location = alembic
sqlalchemy.url = postgresql+asyncpg://user:password@localhost:5432/rag_pipeline
```

### Configure `alembic/env.py` for Async

```python
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

# Import your models so autogenerate can detect them
from src.models.base import Base
from src.models.document import Document
from src.models.chunk import ChunkRecord

config = context.config
fileConfig(config.config_file_name)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    import asyncio
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

---

## Alembic Migration Commands

```bash
# Generate migration from model changes
alembic revision --autogenerate -m "add content_hash to documents"

# Apply all pending migrations
alembic upgrade head

# Apply one migration forward
alembic upgrade +1

# Rollback one migration
alembic downgrade -1

# View current migration state
alembic current

# View migration history
alembic history --verbose

# Show pending migrations
alembic history -r current:head
```

---

## Generated Migration Example

```python
# alembic/versions/xxxx_add_content_hash_to_documents.py
"""add content_hash to documents

Revision ID: a1b2c3d4e5f6
Revises: previous_revision_id
Create Date: 2026-04-19 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = 'previous_revision_id'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'documents',
        sa.Column('content_hash', sa.String(length=64), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('documents', 'content_hash')
```

---

## FastAPI Integration Pattern

```python
from fastapi import FastAPI, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from src.database import get_db

app = FastAPI()

@app.get("/api/v1/documents/{doc_id}")
async def get_document(doc_id: str, db: AsyncSession = Depends(get_db)):
    doc = await get_document_by_id(doc_id, db)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc
```

---

## Common Pitfalls

1. **`asyncpg` driver** — SQLAlchemy async with PostgreSQL requires `asyncpg`. Use `postgresql+asyncpg://` in the URL.
2. **`expire_on_commit=False`** — Without this, accessing model attributes after `commit()` triggers a lazy load, which fails in async context.
3. **`scalars()` vs `all()`** — Use `result.scalars().all()` for ORM objects. Use `result.all()` for raw rows/tuples.
4. **`scalar_one_or_none()`** — Returns `None` if no result, raises if multiple results. Use for unique lookups.
5. **Alembic autogenerate** — Must import all models in `env.py` before `target_metadata = Base.metadata`. Otherwise autogenerate won't detect new tables/columns.
6. **`pool_pre_ping=True`** — Prevents "connection closed" errors after database restarts by testing connections before use.
7. **`String(64)` for SHA-256** — SHA-256 produces 64 hex characters. Always specify length for `String` columns.

---

## Sources
- https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
- https://docs.sqlalchemy.org/en/20/orm/declarative_tables.html
- https://alembic.sqlalchemy.org/en/latest/autogenerate.html
- https://alembic.sqlalchemy.org/en/latest/cookbook.html#using-asyncio-with-alembic
