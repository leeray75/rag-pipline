# Phase 6 — JSON Generation, Chunking & Vector Ingestion

> **Prerequisites**: Phase 5 complete — Human review dashboard working, approve/reject/edit workflow functional, approved documents in staging with `status = "approved"`.
> **Ref**: [phase-0-index.md](phase-0-index.md) for pinned versions.

---

## Objective

Build the Markdown → JSON serialization pipeline with intelligent token-aware chunking, implement the embedding pipeline using **FastEmbed** (local, no API key required) with **BAAI/bge-small-en-v1.5** (primary) or **thenlper/gte-small** (alternative), upsert embedded chunks into Qdrant, and build the JSON review UI for browsing, inspecting, and approving chunks before final ingestion.

---

## Key Version Pins (Phase 6 additions)

| Package | Version | Install |
|---|---|---|
| fastembed | 0.8.0 | `pip install fastembed` |
| tiktoken | 0.12.0 | `pip install tiktoken` |
| qdrant-client | 1.17.1 | already in pyproject.toml |

### Embedding Model Details

| Model | Identifier | Dimensions | Max Tokens | Size |
|---|---|---|---|---|
| BGE-small-en-v1.5 (primary) | `BAAI/bge-small-en-v1.5` | 384 | 512 | ~33M params |
| GTE-small (alternative) | `thenlper/gte-small` | 384 | 512 | ~33M params |

> **Why FastEmbed?** Runs locally with ONNX Runtime — no external API calls, no API keys, no rate limits, deterministic embeddings, fast batch processing. Both models produce 384-dimension vectors with cosine similarity.

---

## Task 1: Add Phase 6 Python Dependencies

**Working directory**: `rag-pipeline/apps/api/`

### 1.1 Update `pyproject.toml` — add to `[project.dependencies]`

```toml
[project.dependencies]
# ... existing deps from Phase 1-5 ...
fastembed = ">=0.8.0,<1.0.0"
tiktoken = ">=0.12.0,<1.0.0"
```

### 1.2 Install and verify

```bash
cd rag-pipeline/apps/api && pip install -e ".[dev]"
```

### 1.3 Verify FastEmbed loads the model

```python
python -c "
from fastembed import TextEmbedding
model = TextEmbedding('BAAI/bge-small-en-v1.5')
embeddings = list(model.embed(['hello world']))
print(f'Dims: {len(embeddings[0])}, Type: {type(embeddings[0])}')
# Expected: Dims: 384, Type: <class 'numpy.ndarray'>
"
```

> **Note**: First run downloads the ONNX model (~50MB). Subsequent runs use the cached model.

**Done when**: `fastembed` imports without errors and produces 384-dim vectors.

---

## Task 2: Create the Chunking Engine

**Working directory**: `rag-pipeline/apps/api/`

### 2.1 Create `src/ingest/chunker.py`

```python
"""Token-aware Markdown chunker with heading-path tracking."""

import uuid
from dataclasses import dataclass, field

import tiktoken


@dataclass
class Chunk:
    """A single chunk extracted from a Markdown document."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    document_id: str = ""
    job_id: str = ""
    chunk_index: int = 0
    total_chunks: int = 0
    content: str = ""
    token_count: int = 0
    heading_path: str = ""
    metadata: dict = field(default_factory=dict)


class MarkdownChunker:
    """Split Markdown into token-bounded chunks preserving heading context.

    Strategy
    --------
    1. Parse the Markdown into sections delimited by headings (# / ## / ###).
    2. For each section, split into paragraphs (double newline).
    3. Greedily accumulate paragraphs until the token budget is reached.
    4. Emit a Chunk with the heading path as context.
    5. If a single paragraph exceeds the budget, split on sentence boundaries.
    """

    def __init__(
        self,
        *,
        target_tokens: int = 512,
        max_tokens: int = 1024,
        overlap_tokens: int = 64,
        encoding_name: str = "cl100k_base",
    ) -> None:
        self.target_tokens = target_tokens
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens
        self.enc = tiktoken.get_encoding(encoding_name)

    def count_tokens(self, text: str) -> int:
        """Return token count for a text string."""
        return len(self.enc.encode(text, disallowed_special=()))

    def chunk_document(
        self,
        *,
        markdown: str,
        document_id: str,
        job_id: str,
        metadata: dict | None = None,
    ) -> list[Chunk]:
        """Chunk a Markdown document into a list of Chunks."""
        sections = self._split_into_sections(markdown)
        raw_chunks: list[str] = []
        heading_paths: list[str] = []

        for heading_path, section_text in sections:
            paragraphs = self._split_paragraphs(section_text)
            section_chunks, section_headings = self._greedy_merge(
                paragraphs, heading_path
            )
            raw_chunks.extend(section_chunks)
            heading_paths.extend(section_headings)

        # Apply overlap between consecutive chunks
        overlapped = self._apply_overlap(raw_chunks)

        # Build Chunk objects
        total = len(overlapped)
        chunks: list[Chunk] = []
        for idx, content in enumerate(overlapped):
            token_count = self.count_tokens(content)
            chunks.append(
                Chunk(
                    document_id=document_id,
                    job_id=job_id,
                    chunk_index=idx,
                    total_chunks=total,
                    content=content,
                    token_count=token_count,
                    heading_path=heading_paths[min(idx, len(heading_paths) - 1)],
                    metadata=metadata or {},
                )
            )
        return chunks

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _split_into_sections(self, markdown: str) -> list[tuple[str, str]]:
        """Split Markdown by headings, returning (heading_path, body) tuples."""
        lines = markdown.split("\n")
        sections: list[tuple[str, str]] = []
        heading_stack: list[str] = []
        current_lines: list[str] = []

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("#"):
                # Flush current section
                if current_lines:
                    path = " > ".join(heading_stack) if heading_stack else "Introduction"
                    sections.append((path, "\n".join(current_lines)))
                    current_lines = []

                # Parse heading level and text
                level = len(stripped) - len(stripped.lstrip("#"))
                heading_text = stripped.lstrip("#").strip()

                # Update heading stack
                while len(heading_stack) >= level:
                    heading_stack.pop()
                heading_stack.append(heading_text)
            else:
                current_lines.append(line)

        # Final section
        if current_lines:
            path = " > ".join(heading_stack) if heading_stack else "Introduction"
            sections.append((path, "\n".join(current_lines)))

        return sections

    def _split_paragraphs(self, text: str) -> list[str]:
        """Split text on double newlines, filtering empties."""
        paragraphs = text.split("\n\n")
        return [p.strip() for p in paragraphs if p.strip()]

    def _greedy_merge(
        self, paragraphs: list[str], heading_path: str
    ) -> tuple[list[str], list[str]]:
        """Greedily merge paragraphs up to target_tokens."""
        chunks: list[str] = []
        headings: list[str] = []
        buffer: list[str] = []
        buffer_tokens = 0

        for para in paragraphs:
            para_tokens = self.count_tokens(para)

            # Single paragraph exceeds max — split on sentences
            if para_tokens > self.max_tokens:
                if buffer:
                    chunks.append("\n\n".join(buffer))
                    headings.append(heading_path)
                    buffer = []
                    buffer_tokens = 0
                sentence_chunks = self._split_long_paragraph(para)
                chunks.extend(sentence_chunks)
                headings.extend([heading_path] * len(sentence_chunks))
                continue

            if buffer_tokens + para_tokens > self.target_tokens and buffer:
                chunks.append("\n\n".join(buffer))
                headings.append(heading_path)
                buffer = []
                buffer_tokens = 0

            buffer.append(para)
            buffer_tokens += para_tokens

        if buffer:
            chunks.append("\n\n".join(buffer))
            headings.append(heading_path)

        return chunks, headings

    def _split_long_paragraph(self, text: str) -> list[str]:
        """Split an oversized paragraph on sentence boundaries."""
        import re

        sentences = re.split(r"(?<=[.!?])\s+", text)
        chunks: list[str] = []
        buffer: list[str] = []
        buffer_tokens = 0

        for sentence in sentences:
            s_tokens = self.count_tokens(sentence)
            if buffer_tokens + s_tokens > self.target_tokens and buffer:
                chunks.append(" ".join(buffer))
                buffer = []
                buffer_tokens = 0
            buffer.append(sentence)
            buffer_tokens += s_tokens

        if buffer:
            chunks.append(" ".join(buffer))

        return chunks

    def _apply_overlap(self, chunks: list[str]) -> list[str]:
        """Add trailing overlap from previous chunk to the start of each chunk."""
        if not chunks or self.overlap_tokens <= 0:
            return chunks

        result = [chunks[0]]
        for i in range(1, len(chunks)):
            prev_tokens = self.enc.encode(chunks[i - 1], disallowed_special=())
            overlap_token_ids = prev_tokens[-self.overlap_tokens :]
            overlap_text = self.enc.decode(overlap_token_ids)
            result.append(f"{overlap_text}\n\n{chunks[i]}")
        return result
```

### 2.2 Create `src/ingest/__init__.py`

```python
"""Ingest package — chunking, embedding, and vector store operations."""
```

**Done when**: `from src.ingest.chunker import MarkdownChunker, Chunk` imports successfully.

---

## Task 3: Create the Embedding Service (FastEmbed)

**Working directory**: `rag-pipeline/apps/api/`

### 3.1 Create `src/embeddings/__init__.py`

```python
"""Embeddings package — FastEmbed model wrappers."""
```

### 3.2 Create `src/embeddings/fastembed_service.py`

```python
"""FastEmbed embedding service — local ONNX-based embeddings.

Uses BAAI/bge-small-en-v1.5 (384 dims) by default.
Alternative: thenlper/gte-small (384 dims).

No API key required. Runs entirely on CPU via ONNX Runtime.
"""

import logging
from typing import Literal

import numpy as np
from fastembed import TextEmbedding

logger = logging.getLogger(__name__)

# Supported model configurations
MODEL_CONFIGS: dict[str, dict] = {
    "BAAI/bge-small-en-v1.5": {
        "dimensions": 384,
        "max_tokens": 512,
        "description": "BGE small English v1.5 — best balance of speed and quality",
    },
    "thenlper/gte-small": {
        "dimensions": 384,
        "max_tokens": 512,
        "description": "GTE small — alternative with similar performance",
    },
}

# Type alias for supported models
ModelName = Literal["BAAI/bge-small-en-v1.5", "thenlper/gte-small"]


class FastEmbedService:
    """Singleton wrapper around FastEmbed TextEmbedding model.

    Usage
    -----
    >>> svc = FastEmbedService(model_name="BAAI/bge-small-en-v1.5")
    >>> vectors = svc.embed_texts(["hello world", "foo bar"])
    >>> len(vectors[0])  # 384
    """

    _instance: "FastEmbedService | None" = None
    _model: TextEmbedding | None = None

    def __init__(
        self,
        model_name: ModelName = "BAAI/bge-small-en-v1.5",
        *,
        cache_dir: str | None = None,
        threads: int | None = None,
    ) -> None:
        if model_name not in MODEL_CONFIGS:
            raise ValueError(
                f"Unsupported model: {model_name}. "
                f"Choose from: {list(MODEL_CONFIGS.keys())}"
            )
        self.model_name = model_name
        self.config = MODEL_CONFIGS[model_name]
        self.dimensions: int = self.config["dimensions"]
        self._cache_dir = cache_dir
        self._threads = threads

    def _get_model(self) -> TextEmbedding:
        """Lazy-load the ONNX model on first use."""
        if self._model is None:
            logger.info(
                "Loading FastEmbed model: %s (dims=%d)",
                self.model_name,
                self.dimensions,
            )
            kwargs: dict = {"model_name": self.model_name}
            if self._cache_dir:
                kwargs["cache_dir"] = self._cache_dir
            if self._threads:
                kwargs["threads"] = self._threads
            self._model = TextEmbedding(**kwargs)
            logger.info("FastEmbed model loaded successfully")
        return self._model

    def embed_texts(self, texts: list[str]) -> list[np.ndarray]:
        """Embed a list of texts, returning a list of numpy arrays.

        Parameters
        ----------
        texts : list[str]
            The texts to embed. Each should be <= 512 tokens for best results.

        Returns
        -------
        list[np.ndarray]
            List of embedding vectors, each of shape (384,).
        """
        model = self._get_model()
        # FastEmbed returns a generator; materialize to list
        embeddings = list(model.embed(texts))
        logger.debug("Embedded %d texts -> %d vectors", len(texts), len(embeddings))
        return embeddings

    def embed_single(self, text: str) -> np.ndarray:
        """Embed a single text string."""
        return self.embed_texts([text])[0]

    def embed_batched(
        self,
        texts: list[str],
        batch_size: int = 100,
    ) -> list[np.ndarray]:
        """Embed texts in batches for memory efficiency.

        Parameters
        ----------
        texts : list[str]
            All texts to embed.
        batch_size : int
            Number of texts per batch (default 100).

        Returns
        -------
        list[np.ndarray]
            All embedding vectors in original order.
        """
        all_embeddings: list[np.ndarray] = []
        total = len(texts)

        for start in range(0, total, batch_size):
            end = min(start + batch_size, total)
            batch = texts[start:end]
            batch_embeddings = self.embed_texts(batch)
            all_embeddings.extend(batch_embeddings)
            logger.info(
                "Embedded batch %d-%d / %d (%.1f%%)",
                start,
                end,
                total,
                (end / total) * 100,
            )

        return all_embeddings
```

### 3.3 Create `src/embeddings/config.py`

```python
"""Embedding configuration loaded from environment variables."""

import os
from dataclasses import dataclass


@dataclass
class EmbeddingConfig:
    """Configuration for the embedding service."""

    model_name: str = os.getenv(
        "EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5"
    )
    dimensions: int = 384
    batch_size: int = int(os.getenv("EMBEDDING_BATCH_SIZE", "100"))
    cache_dir: str | None = os.getenv("FASTEMBED_CACHE_DIR", None)
    threads: int | None = (
        int(os.getenv("FASTEMBED_THREADS"))
        if os.getenv("FASTEMBED_THREADS")
        else None
    )

    def __post_init__(self) -> None:
        """Validate dimensions match model."""
        from src.embeddings.fastembed_service import MODEL_CONFIGS

        if self.model_name in MODEL_CONFIGS:
            self.dimensions = MODEL_CONFIGS[self.model_name]["dimensions"]
```

**Done when**: `from src.embeddings.fastembed_service import FastEmbedService` works, and `FastEmbedService().embed_single("test")` returns a 384-dim `numpy.ndarray`.

---

## Task 4: Create JSON Document Schema & Serialization

**Working directory**: `rag-pipeline/apps/api/`

### 4.1 Create `src/schemas/chunk.py`

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

### 4.2 Create `src/schemas/collection.py`

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

**Done when**: `from src.schemas.chunk import ChunkDocument, EmbedRequest` imports cleanly.

---

## Task 5: Create Database Models for Chunks & Collections

**Working directory**: `rag-pipeline/apps/api/`

### 5.1 Create `src/models/chunk.py`

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

### 5.2 Add relationship to existing Document model

In `src/models/document.py`, add inside the `Document` class:

```python
    # Add this relationship — links to chunks generated from this document
    chunks = relationship(
        "ChunkRecord", back_populates="document", cascade="all, delete-orphan"
    )
```

### 5.3 Generate Alembic migration

```bash
cd rag-pipeline/apps/api
alembic revision --autogenerate -m "add chunks and vector_collections tables"
alembic upgrade head
```

**Done when**: `chunks` and `vector_collections` tables exist in Postgres with all columns.

---

## Task 6: Build the Chunking Pipeline Service

**Working directory**: `rag-pipeline/apps/api/`

### 6.1 Create `src/ingest/chunking_pipeline.py`

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

**Done when**: `ChunkingPipeline().chunk_job(...)` processes a list of approved documents and produces JSON files in `data/staging/chunks/{job_id}/`.

---

## Task 7: Build the Qdrant Ingestion Service

**Working directory**: `rag-pipeline/apps/api/`

### 7.1 Create `src/ingest/qdrant_ingest.py`

```python
"""Qdrant vector ingestion — embeds chunks and upserts to a collection."""

import logging
from typing import AsyncGenerator

import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    Distance,
    PointStruct,
    VectorParams,
)
from sqlalchemy.ext.asyncio import AsyncSession

from src.embeddings.config import EmbeddingConfig
from src.embeddings.fastembed_service import FastEmbedService
from src.models.chunk import ChunkRecord, VectorCollection
from src.schemas.chunk import EmbedProgress

logger = logging.getLogger(__name__)


class QdrantIngestService:
    """Manages embedding and upserting chunks into Qdrant.

    Workflow
    --------
    1. Create or verify the Qdrant collection.
    2. Load all pending ChunkRecords from Postgres.
    3. Embed chunk content in batches using FastEmbed.
    4. Upsert PointStructs to Qdrant with full payload metadata.
    5. Update chunk embedding_status and VectorCollection stats.
    """

    def __init__(
        self,
        *,
        qdrant_url: str = "http://localhost:6333",
        embedding_config: EmbeddingConfig | None = None,
    ) -> None:
        self.qdrant = QdrantClient(url=qdrant_url)
        self.embed_config = embedding_config or EmbeddingConfig()
        self.embed_service = FastEmbedService(
            model_name=self.embed_config.model_name,
            cache_dir=self.embed_config.cache_dir,
            threads=self.embed_config.threads,
        )

    def ensure_collection(self, collection_name: str) -> None:
        """Create the Qdrant collection if it does not exist.

        Uses cosine distance and 384 dimensions (BGE-small / GTE-small).
        """
        collections = self.qdrant.get_collections().collections
        existing = [c.name for c in collections]

        if collection_name in existing:
            logger.info("Collection '%s' already exists", collection_name)
            return

        self.qdrant.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=self.embed_config.dimensions,
                distance=Distance.COSINE,
            ),
        )
        logger.info(
            "Created Qdrant collection '%s' (dims=%d, distance=Cosine)",
            collection_name,
            self.embed_config.dimensions,
        )

    async def ingest_job(
        self,
        *,
        job_id: str,
        collection_name: str,
        db: AsyncSession,
    ) -> AsyncGenerator[EmbedProgress, None]:
        """Embed and upsert all chunks for a job, yielding progress.

        This is an async generator so the caller can stream progress
        over WebSocket.

        Yields
        ------
        EmbedProgress
            Progress updates at each stage.
        """
        from sqlalchemy import select

        # Step 1: Ensure collection
        self.ensure_collection(collection_name)
        yield EmbedProgress(
            job_id=job_id,
            phase="embedding",
            current=0,
            total=0,
            message=f"Collection '{collection_name}' ready",
        )

        # Step 2: Load pending chunks
        stmt = (
            select(ChunkRecord)
            .where(ChunkRecord.job_id == job_id)
            .where(ChunkRecord.embedding_status == "pending")
            .order_by(ChunkRecord.chunk_index)
        )
        result = await db.execute(stmt)
        chunks: list[ChunkRecord] = list(result.scalars().all())
        total = len(chunks)

        if total == 0:
            yield EmbedProgress(
                job_id=job_id,
                phase="complete",
                current=0,
                total=0,
                message="No pending chunks to embed",
            )
            return

        yield EmbedProgress(
            job_id=job_id,
            phase="embedding",
            current=0,
            total=total,
            message=f"Starting embedding of {total} chunks with {self.embed_config.model_name}",
        )

        # Step 3: Embed in batches
        batch_size = self.embed_config.batch_size
        all_embeddings: list[np.ndarray] = []
        embedded_count = 0

        for start in range(0, total, batch_size):
            end = min(start + batch_size, total)
            batch_texts = [c.content for c in chunks[start:end]]

            # Retry logic with exponential backoff
            batch_embeddings = self._embed_with_retry(batch_texts, max_retries=3)
            all_embeddings.extend(batch_embeddings)
            embedded_count = end

            yield EmbedProgress(
                job_id=job_id,
                phase="embedding",
                current=embedded_count,
                total=total,
                message=f"Embedded {embedded_count}/{total} chunks",
            )

        # Step 4: Upsert to Qdrant in batches
        yield EmbedProgress(
            job_id=job_id,
            phase="upserting",
            current=0,
            total=total,
            message="Starting Qdrant upsert",
        )

        upserted_count = 0
        for start in range(0, total, batch_size):
            end = min(start + batch_size, total)
            points = []
            for i in range(start, end):
                chunk = chunks[i]
                embedding = all_embeddings[i]
                payload = {
                    "document_id": str(chunk.document_id),
                    "job_id": str(chunk.job_id),
                    "chunk_index": chunk.chunk_index,
                    "total_chunks": chunk.total_chunks,
                    "content": chunk.content,
                    "token_count": chunk.token_count,
                    "heading_path": chunk.heading_path,
                    **(chunk.metadata_json or {}),
                }
                points.append(
                    PointStruct(
                        id=str(chunk.id),
                        vector=embedding.tolist(),
                        payload=payload,
                    )
                )

            self.qdrant.upsert(
                collection_name=collection_name,
                points=points,
            )

            # Mark chunks as embedded
            for i in range(start, end):
                chunks[i].embedding_status = "embedded"

            upserted_count = end
            yield EmbedProgress(
                job_id=job_id,
                phase="upserting",
                current=upserted_count,
                total=total,
                message=f"Upserted {upserted_count}/{total} vectors",
            )

        # Step 5: Record collection in Postgres
        collection_record = VectorCollection(
            job_id=job_id,
            collection_name=collection_name,
            embedding_model=self.embed_config.model_name,
            vector_dimensions=self.embed_config.dimensions,
            vector_count=total,
            document_count=len(set(str(c.document_id) for c in chunks)),
            status="ready",
        )
        db.add(collection_record)
        await db.commit()

        yield EmbedProgress(
            job_id=job_id,
            phase="complete",
            current=total,
            total=total,
            message=f"Ingestion complete: {total} vectors in '{collection_name}'",
        )

    def _embed_with_retry(
        self,
        texts: list[str],
        max_retries: int = 3,
    ) -> list[np.ndarray]:
        """Embed texts with exponential backoff retry on failure."""
        import time

        for attempt in range(max_retries):
            try:
                return self.embed_service.embed_texts(texts)
            except Exception:
                if attempt == max_retries - 1:
                    raise
                wait = 2**attempt
                logger.warning(
                    "Embedding failed (attempt %d/%d), retrying in %ds",
                    attempt + 1,
                    max_retries,
                    wait,
                )
                time.sleep(wait)
        return []  # unreachable, but satisfies type checker

    def get_collection_stats(self, collection_name: str) -> dict:
        """Query Qdrant for live collection statistics."""
        info = self.qdrant.get_collection(collection_name)
        return {
            "collection_name": collection_name,
            "vector_count": info.vectors_count,
            "indexed_vectors": info.indexed_vectors_count,
            "points_count": info.points_count,
            "segments_count": len(info.segments or []),
            "status": info.status.value if info.status else "unknown",
        }

    def test_similarity_search(
        self,
        *,
        collection_name: str,
        query_text: str,
        limit: int = 5,
    ) -> list[dict]:
        """Run a similarity search to verify ingestion quality.

        Embeds the query text and searches Qdrant.
        """
        query_vector = self.embed_service.embed_single(query_text)
        results = self.qdrant.query_points(
            collection_name=collection_name,
            query=query_vector.tolist(),
            limit=limit,
            with_payload=True,
        )
        return [
            {
                "id": str(point.id),
                "score": point.score,
                "content_preview": (point.payload or {}).get("content", "")[:200],
                "heading_path": (point.payload or {}).get("heading_path", ""),
                "source_url": (point.payload or {}).get("source_url", ""),
            }
            for point in results.points
        ]
```

**Done when**: `QdrantIngestService().ensure_collection("test")` creates a collection in Qdrant with 384 dimensions and cosine distance.

---

## Task 8: Create the Celery Task for Chunking & Embedding

**Working directory**: `rag-pipeline/apps/api/`

### 8.1 Create `src/workers/ingest_tasks.py`

```python
"""Celery tasks for chunking and vector ingestion."""

import asyncio
import json
import logging
from pathlib import Path

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="ingest.chunk_job",
    max_retries=2,
    default_retry_delay=30,
)
def chunk_job_task(self, job_id: str) -> dict:
    """Chunk all approved documents for a job.

    1. Load approved documents from Postgres.
    2. Run the chunking pipeline.
    3. Return chunk statistics.
    """
    from src.database import get_sync_session
    from src.ingest.chunking_pipeline import ChunkingPipeline

    logger.info("Starting chunking task for job %s", job_id)

    # Use sync wrapper around async pipeline
    async def _run() -> dict:
        from sqlalchemy import select
        from src.models.document import Document

        async with get_sync_session() as db:
            stmt = (
                select(Document)
                .where(Document.job_id == job_id)
                .where(Document.status == "approved")
            )
            result = await db.execute(stmt)
            documents = result.scalars().all()

            if not documents:
                return {"error": "No approved documents found", "job_id": job_id}

            approved = []
            for doc in documents:
                staging_path = Path(f"data/staging/markdown/{job_id}/{doc.id}.md")
                if not staging_path.exists():
                    logger.warning("Missing staging file for doc %s", doc.id)
                    continue
                markdown_content = staging_path.read_text(encoding="utf-8")
                approved.append({
                    "document_id": str(doc.id),
                    "markdown_content": markdown_content,
                    "source_url": doc.source_url or "",
                    "title": doc.title or "",
                    "description": doc.description or "",
                    "tags": doc.tags or [],
                    "fetched_at": str(doc.fetched_at) if doc.fetched_at else None,
                    "approved_at": str(doc.approved_at) if doc.approved_at else None,
                    "audit_rounds": doc.audit_rounds or 0,
                    "quality_score": doc.quality_score or 0.0,
                })

            pipeline = ChunkingPipeline()
            stats = await pipeline.chunk_job(
                job_id=job_id,
                approved_documents=approved,
                db=db,
            )
            return stats.model_dump()

    return asyncio.run(_run())


@shared_task(
    bind=True,
    name="ingest.embed_job",
    max_retries=1,
    default_retry_delay=60,
)
def embed_job_task(self, job_id: str, collection_name: str) -> dict:
    """Embed all pending chunks for a job and upsert to Qdrant.

    1. Initialize FastEmbed + Qdrant service.
    2. Ensure collection exists.
    3. Embed + upsert in batches.
    4. Return final progress.
    """
    from src.database import get_sync_session
    from src.ingest.qdrant_ingest import QdrantIngestService

    logger.info(
        "Starting embed task for job %s -> collection '%s'",
        job_id,
        collection_name,
    )

    async def _run() -> dict:
        service = QdrantIngestService()
        async with get_sync_session() as db:
            final_progress = None
            async for progress in service.ingest_job(
                job_id=job_id,
                collection_name=collection_name,
                db=db,
            ):
                final_progress = progress
                logger.info(
                    "[%s] %s: %d/%d — %s",
                    progress.phase,
                    job_id,
                    progress.current,
                    progress.total,
                    progress.message,
                )
            return final_progress.model_dump() if final_progress else {}

    return asyncio.run(_run())
```

**Done when**: Both `chunk_job_task` and `embed_job_task` are registered in the Celery worker and can be invoked via `.delay()`.

---

## Task 9: Create the Ingestion API Router

**Working directory**: `rag-pipeline/apps/api/`

### 9.1 Create `src/routers/ingest.py`

```python
"""Ingestion API — chunking, embedding, and Qdrant management."""

import logging

from fastapi import APIRouter, Depends, HTTPException, WebSocket
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.ingest.qdrant_ingest import QdrantIngestService
from src.models.chunk import ChunkRecord, VectorCollection
from src.schemas.chunk import (
    ChunkDocument,
    ChunkStats,
    EmbedProgress,
    EmbedRequest,
)
from src.schemas.collection import CollectionInfo, CollectionStats
from src.workers.ingest_tasks import chunk_job_task, embed_job_task

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ingest", tags=["ingest"])


# ------------------------------------------------------------------
# Chunking endpoints
# ------------------------------------------------------------------


@router.post("/jobs/{job_id}/chunk", response_model=dict)
async def start_chunking(job_id: str):
    """Trigger chunking of all approved documents for a job.

    Returns a Celery task ID for polling status.
    """
    task = chunk_job_task.delay(job_id)
    return {"task_id": task.id, "job_id": job_id, "status": "chunking_started"}


@router.get("/jobs/{job_id}/chunks", response_model=list[ChunkDocument])
async def list_chunks(
    job_id: str,
    offset: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """List all chunks for a job with pagination."""
    stmt = (
        select(ChunkRecord)
        .where(ChunkRecord.job_id == job_id)
        .order_by(ChunkRecord.chunk_index)
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    records = result.scalars().all()

    return [
        ChunkDocument(
            id=str(r.id),
            document_id=str(r.document_id),
            job_id=str(r.job_id),
            chunk_index=r.chunk_index,
            total_chunks=r.total_chunks,
            content=r.content,
            token_count=r.token_count,
            metadata=r.metadata_json or {},
        )
        for r in records
    ]


@router.get("/jobs/{job_id}/chunks/{chunk_id}", response_model=ChunkDocument)
async def get_chunk(
    job_id: str,
    chunk_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a single chunk by ID."""
    stmt = select(ChunkRecord).where(
        ChunkRecord.id == chunk_id,
        ChunkRecord.job_id == job_id,
    )
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(404, "Chunk not found")

    return ChunkDocument(
        id=str(record.id),
        document_id=str(record.document_id),
        job_id=str(record.job_id),
        chunk_index=record.chunk_index,
        total_chunks=record.total_chunks,
        content=record.content,
        token_count=record.token_count,
        metadata=record.metadata_json or {},
    )


@router.get("/jobs/{job_id}/chunk-stats", response_model=ChunkStats)
async def get_chunk_stats(
    job_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get aggregated chunk statistics for the review UI."""
    stmt = select(ChunkRecord).where(ChunkRecord.job_id == job_id)
    result = await db.execute(stmt)
    records = result.scalars().all()

    if not records:
        raise HTTPException(404, "No chunks found for this job")

    token_counts = [r.token_count for r in records]

    # Compute histogram
    buckets = [0] * 7
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

    return ChunkStats(
        job_id=job_id,
        total_chunks=len(records),
        avg_token_count=sum(token_counts) / len(token_counts),
        min_token_count=min(token_counts),
        max_token_count=max(token_counts),
        total_tokens=sum(token_counts),
        token_histogram=buckets,
    )


# ------------------------------------------------------------------
# Embedding endpoints
# ------------------------------------------------------------------


@router.post("/jobs/{job_id}/embed", response_model=dict)
async def start_embedding(
    job_id: str,
    request: EmbedRequest,
    db: AsyncSession = Depends(get_db),
):
    """Trigger embedding + Qdrant upsert for a job.

    The collection_name must be unique and follow Qdrant naming rules.
    """
    # Check collection name not already taken
    existing = await db.execute(
        select(VectorCollection).where(
            VectorCollection.collection_name == request.collection_name
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            409,
            f"Collection '{request.collection_name}' already exists",
        )

    task = embed_job_task.delay(job_id, request.collection_name)
    return {
        "task_id": task.id,
        "job_id": job_id,
        "collection_name": request.collection_name,
        "status": "embedding_started",
    }


@router.websocket("/jobs/{job_id}/embed/ws")
async def embed_progress_ws(websocket: WebSocket, job_id: str):
    """WebSocket endpoint for real-time embedding progress.

    Streams EmbedProgress events as the embedding pipeline runs.
    """
    await websocket.accept()
    db_gen = get_db()
    db: AsyncSession = await db_gen.__anext__()

    try:
        service = QdrantIngestService()
        # This requires the collection_name — get it from the URL query param
        collection_name = websocket.query_params.get("collection")
        if not collection_name:
            await websocket.send_json(
                {"error": "Missing 'collection' query parameter"}
            )
            await websocket.close()
            return

        async for progress in service.ingest_job(
            job_id=job_id,
            collection_name=collection_name,
            db=db,
        ):
            await websocket.send_json(progress.model_dump())

    except Exception as e:
        logger.exception("Embed WS error for job %s", job_id)
        await websocket.send_json(
            {"error": str(e), "phase": "error", "job_id": job_id}
        )
    finally:
        await websocket.close()
        await db_gen.aclose()


# ------------------------------------------------------------------
# Collection management endpoints
# ------------------------------------------------------------------


@router.get("/collections", response_model=list[CollectionInfo])
async def list_collections(
    db: AsyncSession = Depends(get_db),
):
    """List all Qdrant collections tracked in Postgres."""
    stmt = select(VectorCollection).order_by(
        VectorCollection.created_at.desc()
    )
    result = await db.execute(stmt)
    records = result.scalars().all()
    return [
        CollectionInfo(
            id=str(r.id),
            job_id=str(r.job_id) if r.job_id else "",
            collection_name=r.collection_name,
            embedding_model=r.embedding_model,
            vector_dimensions=r.vector_dimensions,
            vector_count=r.vector_count,
            document_count=r.document_count,
            status=r.status,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in records
    ]


@router.get("/collections/{name}/stats", response_model=CollectionStats)
async def get_collection_stats(name: str):
    """Get live Qdrant statistics for a collection."""
    try:
        service = QdrantIngestService()
        stats = service.get_collection_stats(name)
        return CollectionStats(**stats)
    except Exception as e:
        raise HTTPException(404, f"Collection not found: {e}")


@router.post("/collections/{name}/search", response_model=list[dict])
async def similarity_search(
    name: str,
    query: str,
    limit: int = 5,
):
    """Run a similarity search against a Qdrant collection.

    Used for testing ingestion quality from the dashboard.
    """
    service = QdrantIngestService()
    results = service.test_similarity_search(
        collection_name=name,
        query_text=query,
        limit=limit,
    )
    return results
```

### 9.2 Register the router in `src/main.py`

Add to the existing imports and `app` setup:

```python
from src.routers.ingest import router as ingest_router

app.include_router(ingest_router, prefix="/api/v1")
```

**Done when**: All endpoints return correct responses:
- `POST /api/v1/ingest/jobs/{id}/chunk` → 200 with task_id
- `GET /api/v1/ingest/jobs/{id}/chunks` → 200 with chunk list
- `GET /api/v1/ingest/jobs/{id}/chunk-stats` → 200 with stats
- `POST /api/v1/ingest/jobs/{id}/embed` → 200 with task_id
- `GET /api/v1/ingest/collections` → 200 with list
- `POST /api/v1/ingest/collections/{name}/search` → 200 with results

---

## Task 10: Create the RTK Query Ingest API Slice (Frontend)

**Working directory**: `rag-pipeline/apps/web/`

### 10.1 Create `src/store/ingestApi.ts`

```typescript
import { createApi, fetchBaseQuery } from "@reduxjs/toolkit/query/react";

// ---- Types ----

export interface ChunkMetadata {
  source_url: string;
  title: string;
  description: string;
  tags: string[];
  heading_path: string;
  fetched_at: string | null;
  approved_at: string | null;
  audit_rounds: number;
  quality_score: number;
}

export interface ChunkDocument {
  id: string;
  document_id: string;
  job_id: string;
  chunk_index: number;
  total_chunks: number;
  content: string;
  token_count: number;
  metadata: ChunkMetadata;
}

export interface ChunkStats {
  job_id: string;
  total_chunks: number;
  avg_token_count: number;
  min_token_count: number;
  max_token_count: number;
  total_tokens: number;
  token_histogram: number[];
}

export interface EmbedRequest {
  job_id: string;
  collection_name: string;
  model_name?: string;
}

export interface CollectionInfo {
  id: string;
  job_id: string;
  collection_name: string;
  embedding_model: string;
  vector_dimensions: number;
  vector_count: number;
  document_count: number;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface CollectionStats {
  collection_name: string;
  vector_count: number;
  indexed_vectors: number;
  points_count: number;
  segments_count: number;
  disk_data_size_bytes: number;
  ram_data_size_bytes: number;
  status: string;
}

export interface SearchResult {
  id: string;
  score: number;
  content_preview: string;
  heading_path: string;
  source_url: string;
}

// ---- API Slice ----

export const ingestApi = createApi({
  reducerPath: "ingestApi",
  baseQuery: fetchBaseQuery({ baseUrl: "/api/v1/ingest" }),
  tagTypes: ["Chunks", "ChunkStats", "Collections"],
  endpoints: (builder) => ({
    // Chunking
    startChunking: builder.mutation<{ task_id: string }, string>({
      query: (jobId) => ({
        url: `/jobs/${jobId}/chunk`,
        method: "POST",
      }),
      invalidatesTags: ["Chunks", "ChunkStats"],
    }),

    listChunks: builder.query<
      ChunkDocument[],
      { jobId: string; offset?: number; limit?: number }
    >({
      query: ({ jobId, offset = 0, limit = 50 }) =>
        `/jobs/${jobId}/chunks?offset=${offset}&limit=${limit}`,
      providesTags: ["Chunks"],
    }),

    getChunk: builder.query<
      ChunkDocument,
      { jobId: string; chunkId: string }
    >({
      query: ({ jobId, chunkId }) => `/jobs/${jobId}/chunks/${chunkId}`,
    }),

    getChunkStats: builder.query<ChunkStats, string>({
      query: (jobId) => `/jobs/${jobId}/chunk-stats`,
      providesTags: ["ChunkStats"],
    }),

    // Embedding
    startEmbedding: builder.mutation<
      { task_id: string; collection_name: string },
      EmbedRequest
    >({
      query: (body) => ({
        url: `/jobs/${body.job_id}/embed`,
        method: "POST",
        body,
      }),
      invalidatesTags: ["Collections"],
    }),

    // Collections
    listCollections: builder.query<CollectionInfo[], void>({
      query: () => "/collections",
      providesTags: ["Collections"],
    }),

    getCollectionStats: builder.query<CollectionStats, string>({
      query: (name) => `/collections/${name}/stats`,
    }),

    similaritySearch: builder.mutation<
      SearchResult[],
      { name: string; query: string; limit?: number }
    >({
      query: ({ name, query, limit = 5 }) => ({
        url: `/collections/${name}/search?query=${encodeURIComponent(query)}&limit=${limit}`,
        method: "POST",
      }),
    }),
  }),
});

export const {
  useStartChunkingMutation,
  useListChunksQuery,
  useGetChunkQuery,
  useGetChunkStatsQuery,
  useStartEmbeddingMutation,
  useListCollectionsQuery,
  useGetCollectionStatsQuery,
  useSimilaritySearchMutation,
} = ingestApi;
```

### 10.2 Register in the Redux store

In `src/store/store.ts`, add:

```typescript
import { ingestApi } from "./ingestApi";

export const store = configureStore({
  reducer: {
    // ... existing reducers ...
    [ingestApi.reducerPath]: ingestApi.reducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware()
      // ... existing middleware ...
      .concat(ingestApi.middleware),
});
```

**Done when**: All RTK Query hooks are importable and TypeScript compiles without errors.

---

## Task 11: Build the Chunk Browser UI

**Working directory**: `rag-pipeline/apps/web/`

### 11.1 Create `src/features/ingest/ChunkBrowser.tsx`

```tsx
"use client";

import { useState } from "react";
import {
  useListChunksQuery,
  useGetChunkStatsQuery,
  type ChunkDocument,
} from "@/store/ingestApi";

interface ChunkBrowserProps {
  jobId: string;
}

export function ChunkBrowser({ jobId }: ChunkBrowserProps) {
  const [page, setPage] = useState(0);
  const pageSize = 25;

  const { data: chunks = [], isLoading } = useListChunksQuery({
    jobId,
    offset: page * pageSize,
    limit: pageSize,
  });

  const { data: stats } = useGetChunkStatsQuery(jobId);

  const [selectedChunk, setSelectedChunk] = useState<ChunkDocument | null>(
    null
  );

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="animate-spin h-8 w-8 border-4 border-blue-500 border-t-transparent rounded-full" />
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* Stats summary */}
      {stats && <ChunkStatsCards stats={stats} />}

      {/* Chunk table */}
      <div className="lg:col-span-2">
        <div className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700">
          <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700">
            <h3 className="text-lg font-semibold">
              Chunks ({stats?.total_chunks ?? 0})
            </h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 dark:bg-gray-800">
                <tr>
                  <th className="px-4 py-2 text-left">#</th>
                  <th className="px-4 py-2 text-left">Heading Path</th>
                  <th className="px-4 py-2 text-left">Content Preview</th>
                  <th className="px-4 py-2 text-right">Tokens</th>
                  <th className="px-4 py-2 text-center">Status</th>
                </tr>
              </thead>
              <tbody>
                {chunks.map((chunk) => (
                  <tr
                    key={chunk.id}
                    className="border-t border-gray-100 dark:border-gray-800 hover:bg-blue-50 dark:hover:bg-gray-800 cursor-pointer"
                    onClick={() => setSelectedChunk(chunk)}
                  >
                    <td className="px-4 py-2 font-mono text-xs">
                      {chunk.chunk_index}
                    </td>
                    <td className="px-4 py-2 text-xs text-gray-500 max-w-[200px] truncate">
                      {chunk.metadata.heading_path || "—"}
                    </td>
                    <td className="px-4 py-2 max-w-[300px] truncate">
                      {chunk.content.slice(0, 120)}...
                    </td>
                    <td className="px-4 py-2 text-right font-mono">
                      {chunk.token_count}
                    </td>
                    <td className="px-4 py-2 text-center">
                      <TokenBadge count={chunk.token_count} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {/* Pagination */}
          <div className="flex justify-between items-center px-4 py-3 border-t border-gray-200 dark:border-gray-700">
            <button
              disabled={page === 0}
              onClick={() => setPage((p) => p - 1)}
              className="px-3 py-1 rounded bg-gray-200 dark:bg-gray-700 disabled:opacity-50"
            >
              ← Prev
            </button>
            <span className="text-sm text-gray-500">Page {page + 1}</span>
            <button
              disabled={chunks.length < pageSize}
              onClick={() => setPage((p) => p + 1)}
              className="px-3 py-1 rounded bg-gray-200 dark:bg-gray-700 disabled:opacity-50"
            >
              Next →
            </button>
          </div>
        </div>
      </div>

      {/* Chunk inspector sidebar */}
      <div className="lg:col-span-1">
        {selectedChunk ? (
          <ChunkInspector chunk={selectedChunk} />
        ) : (
          <div className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-6 text-center text-gray-400">
            Click a chunk to inspect
          </div>
        )}
      </div>
    </div>
  );
}

// ---- Sub-components ----

function ChunkStatsCards({ stats }: { stats: import("@/store/ingestApi").ChunkStats }) {
  const bucketLabels = [
    "0-128",
    "128-256",
    "256-384",
    "384-512",
    "512-768",
    "768-1024",
    "1024+",
  ];

  return (
    <div className="lg:col-span-3 grid grid-cols-2 md:grid-cols-4 gap-4">
      <StatCard label="Total Chunks" value={stats.total_chunks} />
      <StatCard
        label="Avg Tokens"
        value={Math.round(stats.avg_token_count)}
      />
      <StatCard label="Min Tokens" value={stats.min_token_count} />
      <StatCard label="Max Tokens" value={stats.max_token_count} />

      {/* Histogram */}
      <div className="col-span-2 md:col-span-4 bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
        <h4 className="text-sm font-medium mb-3">Token Distribution</h4>
        <div className="flex items-end gap-2 h-24">
          {stats.token_histogram.map((count, i) => {
            const max = Math.max(...stats.token_histogram, 1);
            const height = (count / max) * 100;
            return (
              <div key={i} className="flex-1 flex flex-col items-center gap-1">
                <span className="text-xs text-gray-500">{count}</span>
                <div
                  className="w-full bg-blue-500 rounded-t"
                  style={{ height: `${height}%`, minHeight: count > 0 ? 4 : 0 }}
                />
                <span className="text-[10px] text-gray-400">
                  {bucketLabels[i]}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
      <p className="text-xs text-gray-500 uppercase tracking-wide">{label}</p>
      <p className="text-2xl font-bold mt-1">{value.toLocaleString()}</p>
    </div>
  );
}

function TokenBadge({ count }: { count: number }) {
  const color =
    count <= 512
      ? "bg-green-100 text-green-700"
      : count <= 1024
        ? "bg-yellow-100 text-yellow-700"
        : "bg-red-100 text-red-700";
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${color}`}>
      {count <= 512 ? "OK" : count <= 1024 ? "Long" : "Over"}
    </span>
  );
}

function ChunkInspector({ chunk }: { chunk: ChunkDocument }) {
  return (
    <div className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800">
        <h3 className="text-sm font-semibold">
          Chunk #{chunk.chunk_index} of {chunk.total_chunks}
        </h3>
        <p className="text-xs text-gray-500 mt-1 font-mono">{chunk.id}</p>
      </div>

      {/* Metadata */}
      <div className="p-4 space-y-3 text-sm">
        <MetaRow label="Heading" value={chunk.metadata.heading_path} />
        <MetaRow label="Source" value={chunk.metadata.source_url} />
        <MetaRow label="Title" value={chunk.metadata.title} />
        <MetaRow
          label="Tags"
          value={chunk.metadata.tags.join(", ") || "—"}
        />
        <MetaRow label="Tokens" value={String(chunk.token_count)} />
        <MetaRow
          label="Quality"
          value={`${chunk.metadata.quality_score}%`}
        />
        <MetaRow
          label="Audit Rounds"
          value={String(chunk.metadata.audit_rounds)}
        />
      </div>

      {/* Content */}
      <div className="border-t border-gray-200 dark:border-gray-700 p-4">
        <h4 className="text-xs font-medium text-gray-500 mb-2">Content</h4>
        <pre className="text-xs whitespace-pre-wrap bg-gray-50 dark:bg-gray-800 p-3 rounded max-h-80 overflow-y-auto">
          {chunk.content}
        </pre>
      </div>
    </div>
  );
}

function MetaRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-2">
      <span className="text-gray-500 min-w-[80px]">{label}:</span>
      <span className="text-gray-900 dark:text-gray-100 break-all">
        {value || "—"}
      </span>
    </div>
  );
}
```

**Done when**: The `ChunkBrowser` component renders a paginated table with stats cards and a chunk inspector sidebar.

---

## Task 12: Build the Embed-to-Qdrant UI

**Working directory**: `rag-pipeline/apps/web/`

### 12.1 Create `src/features/ingest/EmbedToQdrant.tsx`

```tsx
"use client";

import { useState, useEffect, useRef } from "react";
import {
  useStartEmbeddingMutation,
  useListCollectionsQuery,
  useGetCollectionStatsQuery,
  useSimilaritySearchMutation,
  type EmbedProgress,
  type SearchResult,
} from "@/store/ingestApi";

interface EmbedToQdrantProps {
  jobId: string;
}

export function EmbedToQdrant({ jobId }: EmbedToQdrantProps) {
  const [collectionName, setCollectionName] = useState("");
  const [showConfirm, setShowConfirm] = useState(false);
  const [progress, setProgress] = useState<EmbedProgress | null>(null);
  const [isIngesting, setIsIngesting] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  const [startEmbedding] = useStartEmbeddingMutation();
  const { data: collections = [], refetch: refetchCollections } =
    useListCollectionsQuery();

  const collectionNameValid = /^[a-z][a-z0-9_-]{2,62}$/.test(collectionName);

  async function handleEmbed() {
    if (!collectionNameValid) return;
    setShowConfirm(false);
    setIsIngesting(true);

    // Start the Celery task
    await startEmbedding({
      job_id: jobId,
      collection_name: collectionName,
      model_name: "BAAI/bge-small-en-v1.5",
    });

    // Connect WebSocket for progress
    const wsUrl = `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}/api/v1/ingest/jobs/${jobId}/embed/ws?collection=${collectionName}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      const data: EmbedProgress = JSON.parse(event.data);
      setProgress(data);
      if (data.phase === "complete" || data.phase === "error") {
        setIsIngesting(false);
        refetchCollections();
        ws.close();
      }
    };

    ws.onerror = () => {
      setIsIngesting(false);
      setProgress({
        job_id: jobId,
        phase: "error",
        current: 0,
        total: 0,
        message: "WebSocket connection failed",
      });
    };
  }

  useEffect(() => {
    return () => {
      wsRef.current?.close();
    };
  }, []);

  return (
    <div className="space-y-6">
      {/* Embed form */}
      <div className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-6">
        <h3 className="text-lg font-semibold mb-4">Embed to Qdrant</h3>
        <p className="text-sm text-gray-500 mb-4">
          Embeds all chunks using{" "}
          <code className="bg-gray-100 dark:bg-gray-800 px-1 rounded">
            BAAI/bge-small-en-v1.5
          </code>{" "}
          via FastEmbed (384 dimensions, cosine similarity). Runs locally — no
          API key required.
        </p>

        <div className="flex gap-3 items-end">
          <div className="flex-1">
            <label className="block text-sm font-medium mb-1">
              Collection Name
            </label>
            <input
              type="text"
              value={collectionName}
              onChange={(e) => setCollectionName(e.target.value.toLowerCase())}
              placeholder="my-docs-collection"
              className={`w-full px-3 py-2 border rounded-lg text-sm ${
                collectionName && !collectionNameValid
                  ? "border-red-500"
                  : "border-gray-300 dark:border-gray-600"
              }`}
            />
            {collectionName && !collectionNameValid && (
              <p className="text-xs text-red-500 mt-1">
                Must be 3-63 chars, start with letter, only lowercase/numbers/hyphens/underscores
              </p>
            )}
          </div>
          <button
            disabled={!collectionNameValid || isIngesting}
            onClick={() => setShowConfirm(true)}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isIngesting ? "Ingesting..." : "Embed to Qdrant"}
          </button>
        </div>
      </div>

      {/* Confirm modal */}
      {showConfirm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-gray-900 rounded-lg p-6 max-w-md w-full mx-4">
            <h4 className="text-lg font-semibold mb-2">Confirm Ingestion</h4>
            <div className="text-sm space-y-2 mb-4">
              <p>
                Collection:{" "}
                <code className="bg-gray-100 dark:bg-gray-800 px-1 rounded">
                  {collectionName}
                </code>
              </p>
              <p>Model: BAAI/bge-small-en-v1.5 (384 dims)</p>
              <p>Distance: Cosine</p>
            </div>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setShowConfirm(false)}
                className="px-4 py-2 border rounded-lg text-sm"
              >
                Cancel
              </button>
              <button
                onClick={handleEmbed}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700"
              >
                Confirm & Start
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Progress */}
      {progress && <EmbedProgressBar progress={progress} />}

      {/* Collections list */}
      <CollectionsList collections={collections} />
    </div>
  );
}

// ---- Sub-components ----

function EmbedProgressBar({ progress }: { progress: EmbedProgress }) {
  const pct =
    progress.total > 0
      ? Math.round((progress.current / progress.total) * 100)
      : 0;
  const color =
    progress.phase === "error"
      ? "bg-red-500"
      : progress.phase === "complete"
        ? "bg-green-500"
        : "bg-blue-500";

  return (
    <div className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium capitalize">{progress.phase}</span>
        <span className="text-sm text-gray-500">
          {progress.current} / {progress.total}
        </span>
      </div>
      <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
        <div
          className={`h-2 rounded-full transition-all ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <p className="text-xs text-gray-500 mt-2">{progress.message}</p>
    </div>
  );
}

function CollectionsList({
  collections,
}: {
  collections: import("@/store/ingestApi").CollectionInfo[];
}) {
  const [searchCollection, setSearchCollection] = useState<string | null>(null);

  if (collections.length === 0) {
    return null;
  }

  return (
    <div className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700">
      <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700">
        <h3 className="text-lg font-semibold">Collections</h3>
      </div>
      <div className="divide-y divide-gray-100 dark:divide-gray-800">
        {collections.map((col) => (
          <div key={col.id} className="px-4 py-3">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">{col.collection_name}</p>
                <p className="text-xs text-gray-500">
                  {col.embedding_model} · {col.vector_dimensions}d ·{" "}
                  {col.vector_count} vectors · {col.document_count} docs
                </p>
              </div>
              <div className="flex gap-2">
                <StatusBadge status={col.status} />
                <button
                  onClick={() => setSearchCollection(col.collection_name)}
                  className="px-3 py-1 text-xs bg-gray-100 dark:bg-gray-800 rounded hover:bg-gray-200 dark:hover:bg-gray-700"
                >
                  Test Search
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Search test panel */}
      {searchCollection && (
        <SearchTestPanel
          collectionName={searchCollection}
          onClose={() => setSearchCollection(null)}
        />
      )}
    </div>
  );
}

function SearchTestPanel({
  collectionName,
  onClose,
}: {
  collectionName: string;
  onClose: () => void;
}) {
  const [query, setQuery] = useState("");
  const [search, { data: results, isLoading }] = useSimilaritySearchMutation();

  return (
    <div className="border-t border-gray-200 dark:border-gray-700 p-4">
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-sm font-medium">
          Search: {collectionName}
        </h4>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
          ✕
        </button>
      </div>
      <div className="flex gap-2 mb-3">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Enter search query..."
          className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm"
          onKeyDown={(e) => {
            if (e.key === "Enter" && query.trim()) {
              search({ name: collectionName, query, limit: 5 });
            }
          }}
        />
        <button
          disabled={!query.trim() || isLoading}
          onClick={() => search({ name: collectionName, query, limit: 5 })}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm disabled:opacity-50"
        >
          {isLoading ? "..." : "Search"}
        </button>
      </div>

      {results && (
        <div className="space-y-2">
          {results.map((r: SearchResult) => (
            <div
              key={r.id}
              className="p-3 bg-gray-50 dark:bg-gray-800 rounded text-sm"
            >
              <div className="flex justify-between mb-1">
                <span className="text-xs text-gray-500">{r.heading_path}</span>
                <span className="text-xs font-mono text-blue-600">
                  {r.score.toFixed(4)}
                </span>
              </div>
              <p className="text-xs">{r.content_preview}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    ready: "bg-green-100 text-green-700",
    creating: "bg-yellow-100 text-yellow-700",
    error: "bg-red-100 text-red-700",
  };

  return (
    <span
      className={`px-2 py-0.5 rounded-full text-xs font-medium ${colors[status] ?? "bg-gray-100 text-gray-700"}`}
    >
      {status}
    </span>
  );
}
```

**Done when**: The `EmbedToQdrant` component renders collection name input, confirm modal, progress bar, collections list, and search test panel.

---

## Task 13: Create the Ingest Page

**Working directory**: `rag-pipeline/apps/web/`

### 13.1 Create `src/app/jobs/[jobId]/ingest/page.tsx`

```tsx
import { ChunkBrowser } from "@/features/ingest/ChunkBrowser";
import { EmbedToQdrant } from "@/features/ingest/EmbedToQdrant";

interface IngestPageProps {
  params: Promise<{ jobId: string }>;
}

export default async function IngestPage({ params }: IngestPageProps) {
  const { jobId } = await params;

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 space-y-8">
      <div>
        <h1 className="text-2xl font-bold">Vector Ingestion</h1>
        <p className="text-sm text-gray-500 mt-1">
          Job: <code className="bg-gray-100 dark:bg-gray-800 px-1 rounded">{jobId}</code>
        </p>
      </div>

      {/* Step 1: Browse generated chunks */}
      <section>
        <h2 className="text-lg font-semibold mb-4">1. Review Chunks</h2>
        <ChunkBrowser jobId={jobId} />
      </section>

      {/* Step 2: Embed and ingest */}
      <section>
        <h2 className="text-lg font-semibold mb-4">2. Embed & Ingest</h2>
        <EmbedToQdrant jobId={jobId} />
      </section>
    </div>
  );
}
```

**Done when**: Navigating to `/jobs/{jobId}/ingest` renders both the chunk browser and the embed-to-Qdrant UI.

---

## Task 14: Add Environment Variables

### 14.1 Update `rag-pipeline/apps/api/.env.example`

Append:

```env
# --- Phase 6: Embedding & Ingestion ---
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
EMBEDDING_BATCH_SIZE=100
FASTEMBED_CACHE_DIR=
FASTEMBED_THREADS=
QDRANT_URL=http://localhost:6333
```

### 14.2 Update Docker Compose (if not already set)

In `rag-pipeline/infra/docker-compose.yml`, ensure the Qdrant service has the correct port mapping and the API service has the environment variables:

```yaml
services:
  api:
    environment:
      - EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
      - EMBEDDING_BATCH_SIZE=100
      - QDRANT_URL=http://qdrant:6333

  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
      - "6334:6334"
    volumes:
      - qdrant_data:/qdrant/storage
```

**Done when**: `.env.example` contains all Phase 6 variables and Docker Compose has the correct environment mapping.

---

## Task 15: Write Tests

**Working directory**: `rag-pipeline/apps/api/`

### 15.1 Create `tests/test_chunker.py`

```python
"""Tests for the Markdown chunker."""

import pytest

from src.ingest.chunker import MarkdownChunker


@pytest.fixture
def chunker() -> MarkdownChunker:
    return MarkdownChunker(
        target_tokens=100,
        max_tokens=200,
        overlap_tokens=16,
    )


def test_basic_chunking(chunker: MarkdownChunker):
    """Chunks are produced from multi-section Markdown."""
    md = """# Introduction

This is the intro paragraph.

## Setup

This is the setup section with more content.

### Prerequisites

You need Python 3.13 installed.

## Usage

Run the command to start the server.
"""
    chunks = chunker.chunk_document(
        markdown=md,
        document_id="doc-1",
        job_id="job-1",
    )
    assert len(chunks) > 0
    # All chunks have correct document_id
    for c in chunks:
        assert c.document_id == "doc-1"
        assert c.job_id == "job-1"
        assert c.token_count > 0

    # First chunk index is 0
    assert chunks[0].chunk_index == 0
    # total_chunks is consistent
    assert all(c.total_chunks == len(chunks) for c in chunks)


def test_heading_path_tracking(chunker: MarkdownChunker):
    """Heading paths are tracked correctly."""
    md = """# Top

## Sub A

Content A.

## Sub B

### Deep B

Content B deep.
"""
    chunks = chunker.chunk_document(
        markdown=md,
        document_id="doc-2",
        job_id="job-2",
    )
    paths = [c.heading_path for c in chunks]
    assert any("Sub A" in p for p in paths)
    assert any("Deep B" in p for p in paths)


def test_empty_document(chunker: MarkdownChunker):
    """Empty document produces no chunks (or one empty chunk)."""
    chunks = chunker.chunk_document(
        markdown="",
        document_id="doc-3",
        job_id="job-3",
    )
    # Empty is acceptable — either 0 chunks or 1 with empty content
    assert len(chunks) <= 1


def test_token_counts_within_bounds(chunker: MarkdownChunker):
    """No chunk exceeds max_tokens (excluding overlap)."""
    long_text = "word " * 500  # ~500 tokens
    md = f"# Title\n\n{long_text}"
    chunks = chunker.chunk_document(
        markdown=md,
        document_id="doc-4",
        job_id="job-4",
    )
    # With overlap, chunks may slightly exceed but raw content should be bounded
    for c in chunks:
        assert c.token_count <= chunker.max_tokens + chunker.overlap_tokens + 10
```

### 15.2 Create `tests/test_fastembed_service.py`

```python
"""Tests for FastEmbed service — requires model download on first run."""

import pytest
import numpy as np

from src.embeddings.fastembed_service import FastEmbedService


@pytest.fixture(scope="module")
def embed_service() -> FastEmbedService:
    """Module-scoped to avoid re-loading the ONNX model per test."""
    return FastEmbedService(model_name="BAAI/bge-small-en-v1.5")


def test_embed_single(embed_service: FastEmbedService):
    """Single text embedding returns correct dimensions."""
    vec = embed_service.embed_single("Hello, world!")
    assert isinstance(vec, np.ndarray)
    assert vec.shape == (384,)


def test_embed_multiple(embed_service: FastEmbedService):
    """Batch embedding returns correct count and dimensions."""
    texts = ["First document", "Second document", "Third document"]
    vecs = embed_service.embed_texts(texts)
    assert len(vecs) == 3
    for v in vecs:
        assert v.shape == (384,)


def test_embed_batched(embed_service: FastEmbedService):
    """Batched embedding handles different batch sizes."""
    texts = [f"Document {i}" for i in range(7)]
    vecs = embed_service.embed_batched(texts, batch_size=3)
    assert len(vecs) == 7


def test_invalid_model():
    """Invalid model name raises ValueError."""
    with pytest.raises(ValueError, match="Unsupported model"):
        FastEmbedService(model_name="invalid/model-name")
```

### 15.3 Run tests

```bash
cd rag-pipeline/apps/api && python -m pytest tests/test_chunker.py tests/test_fastembed_service.py -v
```

**Done when**: All tests pass.

---

## Done-When Checklist

| # | Criterion | Verify |
|---|-----------|--------|
| 1 | `fastembed` 0.8.0 installed and `BAAI/bge-small-en-v1.5` loads | `python -c "from fastembed import TextEmbedding; m = TextEmbedding('BAAI/bge-small-en-v1.5'); print(len(list(m.embed(['test']))[0]))"` → 384 |
| 2 | `MarkdownChunker` splits docs with heading-path tracking | `pytest tests/test_chunker.py -v` passes |
| 3 | `FastEmbedService` produces 384-dim numpy arrays | `pytest tests/test_fastembed_service.py -v` passes |
| 4 | `chunks` and `vector_collections` tables exist in Postgres | `alembic upgrade head` succeeds |
| 5 | `ChunkingPipeline.chunk_job()` saves .json files to staging | JSON files appear in `data/staging/chunks/{job_id}/` |
| 6 | `POST /api/v1/ingest/jobs/{id}/chunk` → Celery task starts | Returns `{"task_id": "...", "status": "chunking_started"}` |
| 7 | `GET /api/v1/ingest/jobs/{id}/chunks` → paginated chunk list | Returns array of ChunkDocument objects |
| 8 | `GET /api/v1/ingest/jobs/{id}/chunk-stats` → statistics | Returns ChunkStats with histogram |
| 9 | `POST /api/v1/ingest/jobs/{id}/embed` → Celery embedding task starts | Returns task_id + collection_name |
| 10 | Qdrant collection created with 384 dims + cosine distance | `qdrant.get_collection(name)` returns correct config |
| 11 | All chunks upserted as vectors with full payload | Qdrant dashboard shows correct vector count |
| 12 | `vector_collections` row created with status "ready" | DB query returns the record |
| 13 | `POST /api/v1/ingest/collections/{name}/search` returns results | Similarity search returns scored results |
| 14 | Chunk browser UI renders paginated table + stats | Navigate to `/jobs/{id}/ingest` |
| 15 | Embed-to-Qdrant UI shows progress + collections list + search | Confirm modal → progress bar → collection appears |
| 16 | All Phase 6 tests pass | `pytest tests/ -v -k "chunk or fastembed"` |
