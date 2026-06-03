# Plan: Replace Qdrant Vector Database with pgvector

## Overview

Replace the external Qdrant vector database service with pgvector (PostgreSQL vector extension) in the RAG pipeline project. Since the project already uses PostgreSQL for structured data, pgvector eliminates the need for a separate vector store service, simplifying the infrastructure while maintaining full semantic search capabilities.

## Current State

### Architecture

```
┌─────────────┐     ┌──────────────┐     ┌──────────┐
│   FastAPI   │────▶│   Qdrant     │
│   (API)     │     │  (Vector DB) │
│             │────▶│   PostgreSQL │
│  Celery     │     └──────────┘
│  Worker     │
└─────────────┘
```

### Qdrant Usage Summary

| Aspect | Current Implementation |
|---|---|
| **Docker Image** | `qdrant/qdrant:latest` |
| **Ports** | 6333 (HTTP), 6334 (gRPC) |
| **Python Client** | `qdrant-client>=1.17.1,<2.0.0` |
| **Environment Vars** | `RAG_QDRANT_HOST`, `QDRANT_URL` |
| **Config Fields** | `qdrant_host`, `qdrant_port` in `Settings` |
| **Vector Dimensions** | 384 (BAAI/bge-small-en-v1.5) |
| **Distance Metric** | Cosine |
| **Collection Name** | User-defined (stored in `vector_collections` table) |
| **Payload Fields** | document_id, job_id, chunk_index, total_chunks, content, token_count, heading_path, source_url, metadata |
| **Operations** | create_collection, upsert, similarity_search (query_points), get_collection_stats |

### Files Referencing Qdrant

| File | Purpose | Lines of Impact |
|---|---|---|
| `infra/docker-compose.yml` | Qdrant service definition, API env vars | ~15 lines |
| `infra/docker-compose.dev.yml` | Qdrant service definition, API/celery env vars | ~15 lines |
| `apps/api/pyproject.toml` | `qdrant-client` dependency | 1 line |
| `apps/api/src/config.py` | `qdrant_host`, `qdrant_port` settings | ~4 lines |
| `apps/api/.env.example` | `QDRANT_URL` env var example | 1 line |
| `apps/api/src/ingest/qdrant_ingest.py` | Core vector store service (QdrantIngestService) | ~280 lines (entire file) |
| `apps/api/src/ingest/reingestion.py` | Indirect - invalidates chunks (no Qdrant ref) | 0 lines |
| `apps/api/src/workers/ingest_tasks.py` | Celery task calling QdrantIngestService | ~10 lines |
| `apps/api/src/routers/ingest.py` | API endpoints using QdrantIngestService | ~10 lines |
| `apps/api/src/models/chunk.py` | VectorCollection model references Qdrant in docstrings | ~5 lines |

### Key Qdrant Operations Used

| Operation | Method | Purpose |
|---|---|---|
| Get collections | `qdrant.get_collections()` | List existing collections |
| Create collection | `qdrant.create_collection()` | Initialize collection with vector params |
| Upsert points | `qdrant.upsert()` | Batch insert vectors with payloads |
| Query points | `qdrant.query_points()` | Similarity search with optional payload |
| Get collection info | `qdrant.get_collection()` | Retrieve vector count, status |

---

## Target Architecture

```
┌──────────────────────────┐
│      FastAPI + Celery     │
│  ┌──────────────────────┐│
│  │  SQLAlchemy (async)  ││
│  │  + pgvector extension││
│  └────────┬─────────────┘│
│           │              │
│     ┌─────▼─────┐        │
│     │ PostgreSQL │        │
│     │  + pgvector│        │
│     └───────────┘        │
└──────────────────────────┘
```

### Benefits
- **Simplified infrastructure**: Remove one Docker service to manage
- **Reduced resource usage**: No separate vector database process
- **Single database for all data**: Structured + vector data in one place
- **Easier backups**: One database to back up
- **Transaction support**: Vector operations within PostgreSQL transactions

---

## Changes Required

### 1. Add pgvector Extension to PostgreSQL

**File**: `infra/docker-compose.yml` and `infra/docker-compose.dev.yml`

**Change**: Enable the pgvector extension in the PostgreSQL service initialization.

**Implementation**:
```yaml
  postgres:
    image: pgvector/pgvector:0.8.2-pg17  # Pinned to 0.8.2 (latest, includes CVE-2026-3172 fix)
    environment:
      POSTGRES_USER: rag_user
      POSTGRES_PASSWORD: rag_pass
      POSTGRES_DB: rag_pipeline
    volumes:
      - postgres-data:/var/lib/postgresql/data
      - ./init-pgvector.sql:/docker-entrypoint-initdb.d/01-init-pgvector.sql  # Add this
```

**Note on image version**: Pin to `0.8.2-pg17` explicitly (not the floating `pg17` tag). pgvector 0.8.2 includes a security fix for CVE-2026-3172 (buffer overflow with parallel HNSW index builds). The `pgvector/pgvector` image already has the extension installed — the init SQL just activates it per-database via `CREATE EXTENSION`.

**Create `infra/init-pgvector.sql`**:
```sql
-- Enable the pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;
```

### 2. Create New Vector Store Service

**File**: `apps/api/src/ingest/pgvector_store.py` (new file, replaces `qdrant_ingest.py`)

**Purpose**: Abstract vector store operations to work with pgvector via SQLAlchemy async.

**Key components**:
```python
"""pgvector vector store — embeds chunks and stores vectors in PostgreSQL."""

import numpy as np
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from src.config import settings
from src.embeddings.config import EmbeddingConfig
from src.embeddings.fastembed_service import FastEmbedService
from src.models.chunk import ChunkRecord, VectorCollection


class PgVectorStore:
    """Manages vector storage and retrieval using pgvector in PostgreSQL."""

    def __init__(
        self,
        embedding_config: EmbeddingConfig | None = None,
    ) -> None:
        self.embed_config = embedding_config or EmbeddingConfig()
        self.embed_service = FastEmbedService(
            model_name=self.embed_config.model_name,
            cache_dir=self.embed_config.cache_dir,
            threads=self.embed_config.threads,
        )
        # pgvector table name
        self.table_name = "chunk_vectors"

    async def ensure_table(self, db: AsyncSession) -> None:
        """Create the chunk_vectors table and extension if they don't exist."""
        await db.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await db.execute(text(f"""
            CREATE TABLE IF NOT EXISTS {self.table_name} (
                id UUID PRIMARY KEY,
                collection_name TEXT NOT NULL,
                vector vector({self.embed_config.dimensions}) NOT NULL,
                document_id UUID NOT NULL,
                job_id UUID NOT NULL,
                chunk_index INTEGER NOT NULL,
                total_chunks INTEGER NOT NULL,
                content TEXT NOT NULL,
                token_count INTEGER NOT NULL,
                heading_path TEXT,
                source_url TEXT,
                metadata_json JSONB,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        """))
        await db.execute(text(f"""
            CREATE INDEX IF NOT EXISTS idx_{self.table_name}_collection
            ON {self.table_name} (collection_name);
        """))
        # HNSW index for fast similarity search (optional, for large datasets)
        await db.execute(text(f"""
            CREATE INDEX IF NOT EXISTS idx_{self.table_name}_vector
            ON {self.table_name} USING hnsw (vector vector_cosine_ops)
            WITH (m = 16, ef_construction = 64);
        """))
        await db.commit()

    async def upsert_vectors(
        self,
        collection_name: str,
        chunks: list[ChunkRecord],
        embeddings: list[np.ndarray],
        db: AsyncSession,
    ) -> int:
        """Upsert vector embeddings with payload metadata.

        Returns the number of vectors upserted.
        """
        rows = []
        for i, chunk in enumerate(chunks):
            rows.append({
                "id": str(chunk.id),
                "collection_name": collection_name,
                "vector": embeddings[i].tolist(),
                "document_id": str(chunk.document_id),
                "job_id": str(chunk.job_id),
                "chunk_index": chunk.chunk_index,
                "total_chunks": chunk.total_chunks,
                "content": chunk.content,
                "token_count": chunk.token_count,
                "heading_path": chunk.heading_path,
                "source_url": chunk.metadata_json.get("source_url", "") if chunk.metadata_json else "",
                "metadata_json": chunk.metadata_json or {},
            })

        # Use PostgreSQL UPSERT (ON CONFLICT DO UPDATE)
        stmt = text(f"""
            INSERT INTO {self.table_name} (
                id, collection_name, vector, document_id, job_id,
                chunk_index, total_chunks, content, token_count,
                heading_path, source_url, metadata_json
            ) VALUES (
                :id, :collection_name, :vector, :document_id, :job_id,
                :chunk_index, :total_chunks, :content, :token_count,
                :heading_path, :source_url, :metadata_json
            )
            ON CONFLICT (id) DO UPDATE SET
                vector = EXCLUDED.vector,
                collection_name = EXCLUDED.collection_name,
                content = EXCLUDED.content,
                metadata_json = EXCLUDED.metadata_json
        """)

        for row in rows:
            await db.execute(stmt, row)
        await db.commit()
        return len(rows)

    async def similarity_search(
        self,
        collection_name: str,
        query_vector: list[float],
        limit: int = 5,
        db: AsyncSession | None = None,
    ) -> list[dict]:
        """Run a cosine similarity search using pgvector.

        Uses the <=> (cosine distance) operator for cosine similarity search.
        Score is 1 - cosine_distance = cosine_similarity, in range [0, 1].
        """
        # Build vector literal string for pgvector
        query_vec_str = f"[{','.join(str(v) for v in query_vector)}]"
        stmt = text("""
            SELECT
                id,
                document_id,
                job_id,
                chunk_index,
                total_chunks,
                content,
                token_count,
                heading_path,
                source_url,
                metadata_json,
                1 - (vector <=> :query_vec::vector) AS score
            FROM chunk_vectors
            WHERE collection_name = :collection_name
            ORDER BY vector <=> :query_vec::vector
            LIMIT :limit
        """)
        result = await db.execute(stmt, {
            "query_vec": query_vec_str,
            "collection_name": collection_name,
            "limit": limit,
        })
        rows = result.fetchall()
        return [
            {
                "id": row.id,
                "document_id": row.document_id,
                "content_preview": row.content[:200] if row.content else "",
                "heading_path": row.heading_path,
                "source_url": row.source_url,
                "score": round(float(row.score), 6),
            }
            for row in rows
        ]

    async def get_collection_stats(
        self,
        collection_name: str,
        db: AsyncSession,
    ) -> dict:
        """Get collection statistics from PostgreSQL."""
        result = await db.execute(
            text(f"SELECT COUNT(*) as vector_count FROM {self.table_name} WHERE collection_name = :name"),
            {"name": collection_name},
        )
        vector_count = result.scalar()

        # Get unique document count
        result = await db.execute(
            text(f"SELECT COUNT(DISTINCT document_id) as document_count FROM {self.table_name} WHERE collection_name = :name"),
            {"name": collection_name},
        )
        document_count = result.scalar()

        return {
            "collection_name": collection_name,
            "vector_count": vector_count or 0,
            "indexed_vectors": vector_count or 0,  # pgvector indexes are automatic
            "points_count": vector_count or 0,
            "segments_count": 1,  # Simplified for pgvector
            "status": "ready",
            "index_type": "HNSW",
        }

    async def delete_collection(
        self,
        collection_name: str,
        db: AsyncSession,
    ) -> int:
        """Delete all vectors for a collection. Returns count deleted."""
        result = await db.execute(
            text(f"DELETE FROM {self.table_name} WHERE collection_name = :name"),
            {"name": collection_name},
        )
        await db.commit()
        return result.rowcount
```

### 3. Update `config.py`

**File**: `apps/api/src/config.py`

**Change**: Remove Qdrant-specific settings, add pgvector-related settings.

**Before**:
```python
# Qdrant
qdrant_host: str = "qdrant"
qdrant_port: int = 6333
```

**After**:
```python
# pgvector (uses same PostgreSQL connection)
# No additional config needed — uses database_url from above
```

### 4. Update `pyproject.toml`

**File**: `apps/api/pyproject.toml`

**Change**: Remove `qdrant-client`. **Keep `asyncpg`** (already in dependencies) — pgvector works with asyncpg via raw `text()` SQL. No need to add `psycopg` unless you're switching drivers.

**Before**:
```toml
"qdrant-client>=1.17.1,<2.0.0",
```

**After**:
```toml
# Remove qdrant-client entirely — pgvector uses PostgreSQL via asyncpg
# asyncpg is already in dependencies and works with pgvector via text() SQL
```

**Note**: The plan uses SQLAlchemy's `text()` for vector operations, which works with the existing `asyncpg` driver. No need to add `psycopg[binary]` — that's only needed if switching from asyncpg to psycopg as the primary driver.

### 5. Update `ingest_tasks.py` (Celery Workers)

**File**: `apps/api/src/workers/ingest_tasks.py`

**Change**: Replace `QdrantIngestService` import and usage with `PgVectorStore`.

**Before**:
```python
from src.ingest.qdrant_ingest import QdrantIngestService
...
service = QdrantIngestService()
service.ensure_collection(collection_name)
...
service.qdrant.upsert(collection_name=collection_name, points=points)
```

**After**:
```python
from src.ingest.pgvector_store import PgVectorStore
...
service = PgVectorStore()
async with async_session_factory() as db:
    await service.ensure_table(db)
    ...
    await service.upsert_vectors(collection_name, chunks, all_embeddings, db)
```

### 6. Update `routers/ingest.py`

**File**: `apps/api/src/routers/ingest.py`

**Change**: Replace `QdrantIngestService` with `PgVectorStore`.

**Before**:
```python
from src.ingest.qdrant_ingest import QdrantIngestService
...
service = QdrantIngestService()
results = service.test_similarity_search(...)
stats = service.get_collection_stats(name)
```

**After**:
```python
from src.ingest.pgvector_store import PgVectorStore
...
@router.get("/collections/{name}/stats", response_model=CollectionStats)
async def get_collection_stats(name: str, db: AsyncSession = Depends(get_db)):
    service = PgVectorStore()
    stats = await service.get_collection_stats(name, db)
    return CollectionStats(**stats)

@router.post("/collections/{name}/search", response_model=list[dict])
async def similarity_search(name: str, query: str, limit: int = 5, db: AsyncSession = Depends(get_db)):
    service = PgVectorStore()
    query_vector = service.embed_service.embed_single(query)
    results = await service.similarity_search(name, query_vector.tolist(), limit)
    return results
```

### 7. Update `models/chunk.py`

**File**: `apps/api/src/models/chunk.py`

**Change**: Update docstrings and comments referencing Qdrant.

**Before**:
```python
"""SQLAlchemy ORM models for chunks and vector collections."""
...
class ChunkRecord(Base):
    """...Chunks are the basic unit of text that will be embedded and stored
    in Qdrant for semantic search."""
...
class VectorCollection(Base):
    """Represents a Qdrant vector collection and its associated metadata.
    Each collection corresponds to a single Qdrant collection..."""
```

**After**:
```python
"""SQLAlchemy ORM models for chunks and vector collections."""
...
class ChunkRecord(Base):
    """...Chunks are the basic unit of text that will be embedded and stored
    in PostgreSQL (pgvector) for semantic search."""
...
class VectorCollection(Base):
    """Represents a pgvector collection and its associated metadata.
    Each collection tracks the embedding progress and statistics."""
```

### 8. Update Docker Compose Files

**Files**: `infra/docker-compose.yml`, `infra/docker-compose.dev.yml`

**Change**:
1. Replace `qdrant` service with `pgvector/pgvector:0.8.2-pg17` image
2. Remove Qdrant-related environment variables from API service
3. Remove Qdrant volume and network references

**docker-compose.yml changes**:

Replace:
```yaml
  # --- Qdrant ---
  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
      - "6334:6334"
    volumes:
      - qdrant-data:/qdrant/storage
    environment:
      QDRANT__SERVICE__GRPC_PORT: 6334
    networks:
      - rag-network
```

With:
```yaml
  # --- PostgreSQL (with pgvector) ---
  postgres:
    image: pgvector/pgvector:0.8.2-pg17
    environment:
      POSTGRES_USER: rag_user
      POSTGRES_PASSWORD: rag_pass
      POSTGRES_DB: rag_pipeline
    ports:
      - "5432:5432"
    volumes:
      - postgres-data:/var/lib/postgresql/data
      - ./init-pgvector.sql:/docker-entrypoint-initdb.d/01-init-pgvector.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U rag_user -d rag_pipeline"]
      interval: 5s
      timeout: 5s
      retries: 5
    networks:
      - rag-network
```

Remove from API service environment:
```yaml
      - RAG_QDRANT_HOST=qdrant
      - QDRANT_URL=http://qdrant:6333
```

Remove volume:
```yaml
  qdrant-data:
```

Remove `depends_on: qdrant` from api service in dev compose.

### 9. Update `.env.example`

**File**: `apps/api/.env.example`

**Change**: Remove `QDRANT_URL` line.

**Before**:
```env
QDRANT_URL=http://localhost:6333
```

**After**:
```env
# pgvector uses the same PostgreSQL connection (RAG_DATABASE_URL)
# No separate vector store configuration needed
```

### 10. Create Alembic Migration

**File**: `apps/api/alembic/versions/<timestamp_add_chunk_vectors_table.py>` (new file)

**Purpose**: Add the `chunk_vectors` table as a proper Alembic migration instead of DDL in application code.

**Steps**:
```bash
cd apps/api
alembic revision -m "add_chunk_vectors_table"
```

**Generated migration file**:
```python
"""add chunk_vectors table for pgvector

Revision ID: <auto-generated>
Revises: <previous_revision>
Create Date: <timestamp>
"""
from alembic import op
import sqlalchemy as sa

revision = '<auto-generated>'
down_revision = '<previous_revision>'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create chunk_vectors table with pgvector extension and indexes."""
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Create the chunk_vectors table
    op.create_table(
        'chunk_vectors',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('collection_name', sa.Text(), nullable=False),
        sa.Column('vector', sa.Text(), nullable=False),  # pgvector type handled at runtime
        sa.Column('document_id', sa.UUID(), nullable=False),
        sa.Column('job_id', sa.UUID(), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('total_chunks', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('token_count', sa.Integer(), nullable=False),
        sa.Column('heading_path', sa.String(length=500)),
        sa.Column('source_url', sa.Text()),
        sa.Column('metadata_json', sa.JSON()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Create indexes
    op.create_index('idx_chunk_vectors_collection', 'chunk_vectors', ['collection_name'])
    op.execute("""
        CREATE INDEX idx_chunk_vectors_vector ON chunk_vectors
        USING hnsw (vector vector_cosine_ops) WITH (m = 16, ef_construction = 64)
    """)


def downgrade() -> None:
    """Drop the chunk_vectors table and pgvector extension."""
    op.drop_index('idx_chunk_vectors_vector')
    op.drop_index('idx_chunk_vectors_collection')
    op.drop_table('chunk_vectors')
    op.execute("DROP EXTENSION IF EXISTS vector")
```

**Note**: The `ensure_table()` approach in `PgVectorStore` is fine as a safety net for local development, but the Alembic migration is the source of truth for schema management.

---

### 11. Create Migration Script (Qdrant → pgvector)

**File**: `apps/api/src/ingest/migrate_from_qdrant.py` (new file)

**Purpose**: Script to migrate existing data from Qdrant to pgvector.

```python
"""Migration script: Export data from Qdrant and import into pgvector."""

import asyncio
import logging
from qdrant_client import QdrantClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.config import Settings
from src.database import async_session_factory
from src.ingest.pgvector_store import PgVectorStore
from src.models.chunk import ChunkRecord

logger = logging.getLogger(__name__)


async def migrate_collection(
    collection_name: str,
    qdrant_url: str = "http://localhost:6333",
) -> dict:
    """Migrate a single collection from Qdrant to pgvector.

    Uses scroll() with pagination (scroll_all() does not exist on the Qdrant client).
    """
    # 1. Connect to Qdrant and export all points with pagination
    qdrant = QdrantClient(url=qdrant_url)
    all_points = []
    offset = None
    while True:
        batch, offset = qdrant.scroll(
            collection_name=collection_name,
            offset=offset,
            limit=1000,
            with_payload=True,
            with_vectors=True,
        )
        all_points.extend(batch)
        if offset is None:
            break

    if not all_points:
        logger.warning("No points found in collection '%s'", collection_name)
        return {"migrated": 0, "collection": collection_name}

    # 2. Connect to PostgreSQL and import
    store = PgVectorStore()
    async with async_session_factory() as db:
        # Build a list of (chunk_id, vector, payload) tuples
        points_data = []
        for point in all_points:
            payload = point.payload or {}
            vector = point.vector
            if vector is None:
                logger.warning("Point %s has no vector, skipping", point.id)
                continue
            points_data.append({
                "id": str(point.id),
                "collection_name": collection_name,
                "vector": vector,
                "document_id": payload.get("document_id", ""),
                "job_id": payload.get("job_id", ""),
                "chunk_index": payload.get("chunk_index", 0),
                "total_chunks": payload.get("total_chunks", 1),
                "content": payload.get("content", ""),
                "token_count": payload.get("token_count", 0),
                "heading_path": payload.get("heading_path", ""),
                "source_url": payload.get("source_url", ""),
                "metadata_json": {k: v for k, v in payload.items()
                                  if k not in ("document_id", "job_id", "chunk_index",
                                               "total_chunks", "content", "token_count",
                                               "heading_path", "source_url")},
            })

        # Upsert in batches using upsert_vectors
        batch_size = 100
        migrated = 0
        for i in range(0, len(points_data), batch_size):
            batch = points_data[i:i + batch_size]
            # Use raw SQL upsert for migration (chunks list is synthetic)
            for point_data in batch:
                await db.execute(text("""
                    INSERT INTO chunk_vectors (
                        id, collection_name, vector, document_id, job_id,
                        chunk_index, total_chunks, content, token_count,
                        heading_path, source_url, metadata_json
                    ) VALUES (
                        :id, :collection_name, :vector::vector, :document_id, :job_id,
                        :chunk_index, :total_chunks, :content, :token_count,
                        :heading_path, :source_url, :metadata_json
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        vector = EXCLUDED.vector,
                        collection_name = EXCLUDED.collection_name,
                        content = EXCLUDED.content,
                        metadata_json = EXCLUDED.metadata_json
                """), point_data)
                migrated += 1

            await db.commit()
            logger.info("Migrated %d/%d vectors from '%s'", migrated, len(points_data), collection_name)

    logger.info("Migrated %d vectors from '%s' to pgvector", migrated, collection_name)
    return {"migrated": migrated, "collection": collection_name}


async def main():
    """Run migration for all collections."""
    settings = Settings()
    qdrant_url = f"http://{settings.qdrant_host}:{settings.qdrant_port}"

    # List all collections
    qdrant = QdrantClient(url=qdrant_url)
    collections = [c.name for c in qdrant.get_collections().collections]

    logger.info("Found %d collections to migrate", len(collections))

    for collection_name in collections:
        await migrate_collection(collection_name, qdrant_url)

    logger.info("Migration complete!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
```

---

## Migration Strategy

### Phase 1: Preparation
- [ ] Create `pgvector_store.py` with full implementation
- [ ] Create `init-pgvector.sql`
- [ ] Update Docker Compose files (add pgvector image, remove qdrant)
- [ ] Update `pyproject.toml` dependencies
- [ ] Update `config.py`
- [ ] Update `.env.example`
- [ ] Write unit tests for `PgVectorStore`

### Phase 2: Parallel Run (Dual Write)
- [ ] Keep Qdrant running alongside new pgvector setup
- [ ] Modify ingestion pipeline to write to BOTH Qdrant and pgvector
- [ ] Run ingestion on test data and compare results
- [ ] Validate search accuracy matches between Qdrant and pgvector

### Phase 3: Data Migration
- [ ] Run `migrate_from_qdrant.py` to copy existing data
- [ ] Verify vector counts match between Qdrant and pgvector
- [ ] Run comparison tests: same search results from both stores

### Phase 4: Cutover
- [ ] Update API to read from pgvector only
- [ ] Deploy updated code
- [ ] Verify search functionality works
- [ ] Monitor error rates and search quality

### Phase 5: Cleanup
- [ ] Remove Qdrant Docker service
- [ ] Remove `qdrant-client` dependency
- [ ] Remove Qdrant-related code files
- [ ] Remove Qdrant environment variables
- [ ] Update documentation
- [ ] Clean up Docker volumes: `docker volume prune`

---

## Environment Variables Reference

| Variable | Before (Qdrant) | After (pgvector) | Description |
|---|---|---|---|
| `RAG_DATABASE_URL` | `postgresql+asyncpg://...` | `postgresql+asyncpg://...` | Unchanged — already used for PostgreSQL |
| `RAG_QDRANT_HOST` | `qdrant` | **REMOVED** | No longer needed |
| `QDRANT_URL` | `http://qdrant:6333` | **REMOVED** | No longer needed |
| `EMBEDDING_MODEL` | `BAAI/bge-small-en-v1.5` | `BAAI/bge-small-en-v1.5` | Unchanged |
| `EMBEDDING_BATCH_SIZE` | `100` | `100` | Unchanged |

---

## Docker Image Changes

| Service | Before | After |
|---|---|---|
| PostgreSQL | `postgres:17` | `pgvector/pgvector:0.8.2-pg17` (pinned, includes CVE-2026-3172 fix) |
| Qdrant | `qdrant/qdrant:latest` | **REMOVED** |

---

## PostgreSQL Table Schema (pgvector)

```sql
CREATE TABLE chunk_vectors (
    id UUID PRIMARY KEY,
    collection_name TEXT NOT NULL,
    vector vector(384) NOT NULL,           -- pgvector type, 384 dims for BGE-small
    document_id UUID NOT NULL,
    job_id UUID NOT NULL,
    chunk_index INTEGER NOT NULL,
    total_chunks INTEGER NOT NULL,
    content TEXT NOT NULL,
    token_count INTEGER NOT NULL,
    heading_path TEXT,
    source_url TEXT,
    metadata_json JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_chunk_vectors_collection ON chunk_vectors (collection_name);
CREATE INDEX idx_chunk_vectors_vector ON chunk_vectors
    USING hnsw (vector vector_cosine_ops) WITH (m = 16, ef_construction = 64);

-- Optional: GiST index for exact nearest neighbor (slower but more accurate)
-- CREATE INDEX idx_chunk_vectors_vector_gist ON chunk_vectors
--     USING gist (vector vector_cosine_ops);
```

---

## Performance Considerations

| Aspect | Qdrant | pgvector |
|---|---|---|
| **Index Type** | IVF + HNSW | HNSW (via pgvector) |
| **Search Speed** | ~1-10ms (dedicated) | ~5-50ms (shared DB) |
| **Scalability** | Horizontal, distributed | Vertical (single DB) |
| **Memory** | Dedicated process | Shared with PostgreSQL |
| **Best For** | Millions+ vectors | Up to ~1M vectors |
| **Operational Complexity** | Higher (separate service) | Lower (single DB) |

### Recommendations for pgvector

1. **Use HNSW index** for sub-linear search time on large datasets
2. **Tune `m` and `ef_construction`** parameters based on dataset size:
   - Small (< 10K vectors): `m=16, ef_construction=64`
   - Medium (10K-100K): `m=32, ef_construction=128`
   - Large (100K-1M): `m=64, ef_construction=256`
3. **Use `ef_search`** runtime parameter to balance speed/accuracy:
   ```sql
   SET hnsw.ef_search = 100;  -- higher = more accurate, slower
   ```
4. **Vacuum and analyze** regularly to maintain performance
5. **Monitor table bloat** and run `VACUUM ANALYZE chunk_vectors` periodically

---

## Risk Assessment

| Risk | Level | Mitigation |
|---|---|---|
| Performance degradation with large datasets | Medium | HNSW indexing; monitor search latency; scale PostgreSQL if needed |
| Data loss during migration | Low | Dual-write phase; verify counts post-migration |
| Increased PostgreSQL memory usage | Medium | Monitor PostgreSQL memory; allocate sufficient resources |
| Query plan regression for other tables | Low | Use connection pooling; isolate vector queries |
| Loss of distributed search capabilities | Low-Medium | pgvector is single-node; consider Cloud SQL/pgbouncer for scaling |
| Downtime during cutover | Low | Run dual-write phase; rollback by re-enabling Qdrant |

---

## Rollback Plan

Since the migration is phased, rollback is straightforward at each step:

1. **If pgvector setup fails**: Keep Qdrant running; do not remove it until cutover is verified
2. **If search quality degrades**: Switch back to Qdrant by reverting the router changes
3. **If PostgreSQL performance degrades**: Increase PostgreSQL resources or re-add Qdrant

**Quick rollback commands**:
```bash
# Revert Docker Compose to use Qdrant
cd rag-pipline/infra
git checkout HEAD~1 docker-compose.yml docker-compose.dev.yml
docker compose -f docker-compose.dev.yml up -d

# Revert API code
git checkout HEAD~1 apps/api/src/ingest/ apps/api/src/routers/ingest.py
docker compose -f docker-compose.dev.yml up -d --force-recreate api celery-worker
```

---

## Files Modified Summary

| File | Action | Description |
|---|---|---|
| `apps/api/src/ingest/pgvector_store.py` | **NEW** | pgvector vector store service (replaces qdrant_ingest.py) |
| `apps/api/src/ingest/migrate_from_qdrant.py` | **NEW** | Migration script from Qdrant to pgvector |
| `apps/api/src/ingest/qdrant_ingest.py` | **DELETE** | Old Qdrant service |
| `apps/api/src/workers/ingest_tasks.py` | Modify | Use PgVectorStore instead of QdrantIngestService |
| `apps/api/src/routers/ingest.py` | Modify | Use PgVectorStore for search/stats endpoints |
| `apps/api/src/models/chunk.py` | Modify | Update docstrings referencing Qdrant |
| `apps/api/src/config.py` | Modify | Remove qdrant_host, qdrant_port settings |
| `apps/api/pyproject.toml` | Modify | Remove qdrant-client only (keep asyncpg) |
| `apps/api/.env.example` | Modify | Remove QDRANT_URL |
| `infra/docker-compose.yml` | Modify | Replace Qdrant with pgvector-enabled PostgreSQL |
| `infra/docker-compose.dev.yml` | Modify | Replace Qdrant with pgvector-enabled PostgreSQL |
| `infra/init-pgvector.sql` | **NEW** | SQL to enable pgvector extension |

---

## Estimated Effort

| Phase | Description | Estimated Time |
|---|---|---|
| Phase 1 | Preparation (code changes, config updates) | 4-6 hours |
| Phase 2 | Parallel run (dual-write testing) | 2-3 hours |
| Phase 3 | Data migration | 1-2 hours |
| Phase 4 | Cutover | 1-2 hours |
| Phase 5 | Cleanup | 1-2 hours |
| **Total** | | **9-15 hours** |

---

## Testing Checklist

- [ ] Verify pgvector extension loads correctly on PostgreSQL startup
- [ ] Test chunk_vectors table creation with all indexes
- [ ] Test vector upsert with various embedding sizes
- [ ] Test similarity search returns correct results (cosine distance)
- [ ] Compare search results between Qdrant and pgvector (dual-write phase)
- [ ] Test migration script with real data
- [ ] Verify vector counts match post-migration
- [ ] Test collection stats endpoint
- [ ] Test collection deletion
- [ ] Verify Docker Compose starts without Qdrant
- [ ] Run existing test suite (if available)
- [ ] Load test: verify search latency with 10K, 100K vectors
- [ ] Test failover/rollback procedure