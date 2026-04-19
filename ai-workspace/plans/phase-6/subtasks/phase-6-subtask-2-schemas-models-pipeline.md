# Phase 6, Subtask 2 — JSON Schemas + Database Models + Chunking Pipeline

> **Phase**: Phase 6 — JSON Generation, Chunking & Vector Ingestion
> **Prerequisites**: Phase 5 complete + Phase 6 Subtask 1 complete (chunker.py, fastembed_service.py, tiktoken/fastembed installed)
> **Subtask Scope**: Tasks 4–6 from Phase 6 (Pydantic schemas, SQLAlchemy models, Alembic migration, ChunkingPipeline service)

---

## Files to Create / Modify

| Action | File Path |
|--------|-----------|
| Create | `rag-pipeline/apps/api/src/schemas/chunk.py` |
| Create | `rag-pipeline/apps/api/src/schemas/collection.py` |
| Create | `rag-pipeline/apps/api/src/models/chunk.py` |
| Modify | `rag-pipeline/apps/api/src/models/document.py` |
| Create | `rag-pipeline/apps/api/alembic/versions/xxx_add_chunks_and_vector_collections.py` |
| Create | `rag-pipeline/apps/api/src/ingest/chunking_pipeline.py` |

---

## Relevant Technology Stack

| Package | Version | Notes |
|---------|---------|-------|
| Python | 3.13.x | Runtime |
| Pydantic | 2.13.0 | Schema definitions |
| SQLAlchemy | 2.0.49 | ORM models |
| Alembic | 1.18.4 | Database migrations |
| tiktoken | 0.12.0 | Token counting (via chunker from Subtask 1) |

---

## Step-by-Step Implementation

### Task 4: Create JSON Document Schema & Serialization

**Working directory**: `rag-pipeline/apps/api/`

#### 4.1 Create `src/schemas/chunk.py`

```python
"""Pydantic schemas for JSON chunk documents."""

from datetime import datetime

from pydantic import BaseModel, Field


class ChunkMetadata(BaseModel):
    """Metadata attached to each chunk for Qdrant payload filtering."""

    source_url: str
    title: str = ""
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    heading_path: str = ""
    fetched_at: datetime | None = None
    approved_at: datetime | None = None
    audit_rounds: int = 0
    quality_score: float = 0.0


class ChunkDocument(BaseModel):
    """The full JSON document stored per chunk — serialized to staging."""

    id: str
    document_id: str
    job_id: str
    chunk_index: int
    total_chunks: int
    content: str
    token_count: int
    metadata: ChunkMetadata

    class Config:
        json_schema_extra = {
            "example": {
                "id": "c1a2b3c4-d5e6-f7a8-b9c0-d1e2f3a4b5c6",
                "document_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "job_id": "j1k2l3m4-n5o6-p7q8-r9s0-t1u2v3w4x5y6",
                "chunk_index": 0,
                "total_chunks": 8,
                "content": "The full text of this chunk...",
                "token_count": 487,
                "metadata": {
                    "source_url": "https://example.com/docs/getting-started",
                    "title": "Getting Started with MCP",
                    "description": "Introduction to the Model Context Protocol",
                    "tags": ["mcp", "protocol", "getting-started"],
                    "heading_path": "Introduction > What is MCP > Core Concepts",
                    "fetched_at": "2025-01-01T00:00:00Z",
                    "approved_at": "2025-01-02T00:00:00Z",
                    "audit_rounds": 2,
                    "quality_score": 94.0,
                },
            }
        }


class ChunkStats(BaseModel):
    """Statistics for a batch of chunks — used by the review UI."""

    job_id: str
    total_chunks: int
    avg_token_count: float
    min_token_count: int
    max_token_count: int
    total_tokens: int
    token_histogram: list[int] = Field(
        default_factory=list,
        description="Bucket counts for token ranges: 0-128, 128-256, 256-384, 384-512, 512-768, 768-1024, 1024+",
    )


class EmbedRequest(BaseModel):
    """Request to embed and ingest chunks for a job."""

    job_id: str
    collection_name: str = Field(
        ...,
        pattern=r"^[a-z][a-z0-9_-]{2,62}$",
        description="Qdrant collection name (lowercase, 3-63 chars, starts with letter)",
    )
    model_name: str = "BAAI/bge-small-en-v1.5"


class EmbedProgress(BaseModel):
    """WebSocket progress update during embedding."""

    job_id: str
    phase: str  # "embedding" | "upserting" | "complete" | "error"
    current: int
    total: int
    message: str
```

#### 4.2 Create `src/schemas/collection.py`

```python
"""Pydantic schemas for Qdrant collection metadata."""

from datetime import datetime

from pydantic import BaseModel


class CollectionInfo(BaseModel):
    """Collection metadata stored in Postgres and returned by API."""

    id: str
    job_id: str
    collection_name: str
    embedding_model: str
    vector_dimensions: int
    vector_count: int
    document_count: int
    status: str  # "creating" | "ready" | "error"
    created_at: datetime
    updated_at: datetime


class CollectionStats(BaseModel):
    """Live stats queried from Qdrant for a collection."""

    collection_name: str
    vector_count: int
    indexed_vectors: int
    points_count: int
    segments_count: int
    disk_data_size_bytes: int
    ram_data_size_bytes: int
    status: str
```

---

### Task 5: Create Database Models for Chunks & Collections

**Working directory**: `rag-pipeline/apps/api/`

#### 5.1 Create `src/models/chunk.py`

```python
"""SQLAlchemy models for JSON chunks and vector collections."""

import uuid

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDMixin


class ChunkRecord(Base, UUIDMixin, TimestampMixin):
    """A staged JSON chunk awaiting embedding.

    Stored in Postgres for the review UI; the actual content
    is also saved as .json files on disk in staging.
    """

    __tablename__ = "chunks"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    total_chunks: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    heading_path: Mapped[str] = mapped_column(String(500), default="")
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    embedding_status: Mapped[str] = mapped_column(
        String(20), default="pending"
    )  # pending | embedded | error

    # Relationships
    document = relationship("Document", back_populates="chunks")


class VectorCollection(Base, UUIDMixin, TimestampMixin):
    """Tracks Qdrant collections created by the pipeline."""

    __tablename__ = "vector_collections"

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    collection_name: Mapped[str] = mapped_column(
        String(63), unique=True, nullable=False, index=True
    )
    embedding_model: Mapped[str] = mapped_column(
        String(100), nullable=False, default="BAAI/bge-small-en-v1.5"
    )
    vector_dimensions: Mapped[int] = mapped_column(
        Integer, nullable=False, default=384
    )
    vector_count: Mapped[int] = mapped_column(Integer, default=0)
    document_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(
        String(20), default="creating"
    )  # creating | ready | error
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
```

#### 5.2 Add relationship to existing Document model

In `src/models/document.py`, add inside the `Document` class:

```python
    # Add this relationship — links to chunks generated from this document
    chunks = relationship(
        "ChunkRecord", back_populates="document", cascade="all, delete-orphan"
    )
```

#### 5.3 Generate Alembic migration

```bash
cd rag-pipeline/apps/api
alembic revision --autogenerate -m "add chunks and vector_collections tables"
alembic upgrade head
```

---

### Task 6: Build the Chunking Pipeline Service

**Working directory**: `rag-pipeline/apps/api/`

#### 6.1 Create `src/ingest/chunking_pipeline.py`

```python
"""End-to-end chunking pipeline: load approved docs -> chunk -> persist."""

import json
import logging
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from src.ingest.chunker import Chunk, MarkdownChunker
from src.models.chunk import ChunkRecord
from src.schemas.chunk import ChunkDocument, ChunkMetadata, ChunkStats

logger = logging.getLogger(__name__)

# Staging directory for JSON chunk files
CHUNK_STAGING_DIR = Path("data/staging/chunks")


class ChunkingPipeline:
    """Orchestrates the Markdown -> JSON chunking process."""

    def __init__(
        self,
        *,
        target_tokens: int = 512,
        max_tokens: int = 1024,
        overlap_tokens: int = 64,
    ) -> None:
        self.chunker = MarkdownChunker(
            target_tokens=target_tokens,
            max_tokens=max_tokens,
            overlap_tokens=overlap_tokens,
        )

    async def chunk_document(
        self,
        *,
        document_id: str,
        job_id: str,
        markdown_content: str,
        source_url: str,
        title: str,
        description: str,
        tags: list[str],
        fetched_at: str | None,
        approved_at: str | None,
        audit_rounds: int,
        quality_score: float,
        db: AsyncSession,
    ) -> list[ChunkDocument]:
        """Chunk a single approved document and persist to DB + disk.

        Steps
        -----
        1. Run MarkdownChunker to produce Chunk dataclasses.
        2. Convert each Chunk to a ChunkDocument Pydantic model.
        3. Save each ChunkDocument as a .json file in staging.
        4. Insert ChunkRecord rows into Postgres.
        5. Return the list of ChunkDocument models.
        """
        # Step 1: Chunk
        chunks: list[Chunk] = self.chunker.chunk_document(
            markdown=markdown_content,
            document_id=document_id,
            job_id=job_id,
        )
        logger.info(
            "Document %s chunked into %d chunks", document_id, len(chunks)
        )

        # Step 2: Convert to Pydantic models
        chunk_docs: list[ChunkDocument] = []
        for chunk in chunks:
            meta = ChunkMetadata(
                source_url=source_url,
                title=title,
                description=description,
                tags=tags,
                heading_path=chunk.heading_path,
                fetched_at=fetched_at,
                approved_at=approved_at,
                audit_rounds=audit_rounds,
                quality_score=quality_score,
            )
            doc = ChunkDocument(
                id=chunk.id,
                document_id=document_id,
                job_id=job_id,
                chunk_index=chunk.chunk_index,
                total_chunks=chunk.total_chunks,
                content=chunk.content,
                token_count=chunk.token_count,
                metadata=meta,
            )
            chunk_docs.append(doc)

        # Step 3: Save JSON files to staging
        job_dir = CHUNK_STAGING_DIR / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        for doc in chunk_docs:
            file_path = job_dir / f"{doc.id}.json"
            file_path.write_text(
                doc.model_dump_json(indent=2), encoding="utf-8"
            )

        # Step 4: Insert into Postgres
        for doc in chunk_docs:
            record = ChunkRecord(
                id=doc.id,
                document_id=doc.document_id,
                job_id=doc.job_id,
                chunk_index=doc.chunk_index,
                total_chunks=doc.total_chunks,
                content=doc.content,
                token_count=doc.token_count,
                heading_path=doc.metadata.heading_path,
                metadata_json=doc.metadata.model_dump(mode="json"),
                embedding_status="pending",
            )
            db.add(record)

        await db.flush()
        logger.info(
            "Persisted %d chunk records for document %s",
            len(chunk_docs),
            document_id,
        )

        return chunk_docs

    async def chunk_job(
        self,
        *,
        job_id: str,
        approved_documents: list[dict],
        db: AsyncSession,
    ) -> ChunkStats:
        """Chunk ALL approved documents for a job.

        Parameters
        ----------
        job_id : str
            The ingestion job ID.
        approved_documents : list[dict]
            Each dict must have keys: document_id, markdown_content,
            source_url, title, description, tags, fetched_at,
            approved_at, audit_rounds, quality_score.
        db : AsyncSession
            Database session.

        Returns
        -------
        ChunkStats
            Aggregated statistics for the UI.
        """
        all_chunks: list[ChunkDocument] = []

        for doc_data in approved_documents:
            chunks = await self.chunk_document(
                document_id=doc_data["document_id"],
                job_id=job_id,
                markdown_content=doc_data["markdown_content"],
                source_url=doc_data["source_url"],
                title=doc_data.get("title", ""),
                description=doc_data.get("description", ""),
                tags=doc_data.get("tags", []),
                fetched_at=doc_data.get("fetched_at"),
                approved_at=doc_data.get("approved_at"),
                audit_rounds=doc_data.get("audit_rounds", 0),
                quality_score=doc_data.get("quality_score", 0.0),
                db=db,
            )
            all_chunks.extend(chunks)

        await db.commit()

        # Compute stats
        token_counts = [c.token_count for c in all_chunks]
        histogram = self._compute_histogram(token_counts)

        return ChunkStats(
            job_id=job_id,
            total_chunks=len(all_chunks),
            avg_token_count=sum(token_counts) / max(len(token_counts), 1),
            min_token_count=min(token_counts, default=0),
            max_token_count=max(token_counts, default=0),
            total_tokens=sum(token_counts),
            token_histogram=histogram,
        )

    @staticmethod
    def _compute_histogram(token_counts: list[int]) -> list[int]:
        """Bucket token counts into ranges for the UI histogram."""
        buckets = [0] * 7  # 0-128, 128-256, 256-384, 384-512, 512-768, 768-1024, 1024+
        boundaries = [128, 256, 384, 512, 768, 1024]
        for count in token_counts:
            placed = False
            for i, boundary in enumerate(boundaries):
                if count <= boundary:
                    buckets[i] += 1
                    placed = True
                    break
            if not placed:
                buckets[-1] += 1
        return buckets
```

---

## Done-When Checklist

| # | Criterion | Verify |
|---|-----------|--------|
| 1 | `from src.schemas.chunk import ChunkDocument, EmbedRequest` imports cleanly | Python import check |
| 2 | `from src.schemas.collection import CollectionInfo, CollectionStats` imports cleanly | Python import check |
| 3 | `chunks` and `vector_collections` tables exist in Postgres | `alembic upgrade head` succeeds |
| 4 | `Document` model has `chunks` relationship | Import and inspect relationship |
| 5 | `ChunkingPipeline().chunk_job(...)` processes approved documents | JSON files appear in `data/staging/chunks/{job_id}/` |
| 6 | ChunkRecord rows inserted into Postgres with `embedding_status = "pending"` | DB query verification |

---

## Summary Report

Upon completion of this subtask, create a summary report at:
`rag-pipeline/ai-workspace/summary-reports/phase-6-subtask-2-schemas-models-pipeline-summary.md`

The summary report must include:
- **Subtask**: Phase 6, Subtask 2 — JSON Schemas + Database Models + Chunking Pipeline
- **Status**: Complete / Partial / Blocked
- **Date**: {ISO 8601 date}
- **Files Created/Modified**: List every file path
- **Key Decisions**: Any deviations from the plan and why
- **Issues Encountered**: Problems and resolutions
- **Dependencies for Next Subtask**: What the next subtask needs to know
- **Verification Results**: Output of Done-When checklist items
