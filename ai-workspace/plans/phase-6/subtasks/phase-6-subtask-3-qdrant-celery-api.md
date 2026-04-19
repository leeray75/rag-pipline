# Phase 6, Subtask 3 — Qdrant Ingestion Service + Celery Tasks + API Router

> **Phase**: Phase 6 — JSON Generation, Chunking & Vector Ingestion
> **Prerequisites**: Phase 5 complete + Phase 6 Subtasks 1–2 complete (chunker, FastEmbedService, schemas, models, ChunkingPipeline all working)
> **Subtask Scope**: Tasks 7–9 from Phase 6 (QdrantIngestService, Celery ingest tasks, FastAPI ingest router)

---

## Files to Create / Modify

| Action | File Path |
|--------|-----------|
| Create | `rag-pipeline/apps/api/src/ingest/qdrant_ingest.py` |
| Create | `rag-pipeline/apps/api/src/workers/ingest_tasks.py` |
| Create | `rag-pipeline/apps/api/src/routers/ingest.py` |
| Modify | `rag-pipeline/apps/api/src/main.py` |

---

## Relevant Technology Stack

| Package | Version | Notes |
|---------|---------|-------|
| Python | 3.13.x | Runtime |
| FastAPI | 0.135.3 | API framework |
| qdrant-client | 1.17.1 | Vector DB client |
| fastembed | 0.8.0 | Embedding (from Subtask 1) |
| Celery | 5.6.3 | Task queue |
| SQLAlchemy | 2.0.49 | ORM |
| Pydantic | 2.13.0 | Schemas |

---

## Context: Key Types from Prior Subtasks

These types were created in Subtask 1 and 2 and are imported here:

- `FastEmbedService` from `src.embeddings.fastembed_service` — embed_texts, embed_single, embed_batched
- `EmbeddingConfig` from `src.embeddings.config` — model_name, dimensions, batch_size
- `ChunkRecord`, `VectorCollection` from `src.models.chunk` — SQLAlchemy models
- `ChunkDocument`, `ChunkStats`, `EmbedProgress`, `EmbedRequest` from `src.schemas.chunk`
- `CollectionInfo`, `CollectionStats` from `src.schemas.collection`
- `ChunkingPipeline` from `src.ingest.chunking_pipeline`

---

## Step-by-Step Implementation

### Task 7: Build the Qdrant Ingestion Service

**Working directory**: `rag-pipeline/apps/api/`

#### 7.1 Create `src/ingest/qdrant_ingest.py`

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
        """Run a similarity search to verify ingestion quality."""
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

---

### Task 8: Create the Celery Tasks for Chunking & Embedding

**Working directory**: `rag-pipeline/apps/api/`

#### 8.1 Create `src/workers/ingest_tasks.py`

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

---

### Task 9: Create the Ingestion API Router

**Working directory**: `rag-pipeline/apps/api/`

#### 9.1 Create `src/routers/ingest.py`

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
    """Trigger chunking of all approved documents for a job."""
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
    """Trigger embedding + Qdrant upsert for a job."""
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
    """WebSocket endpoint for real-time embedding progress."""
    await websocket.accept()
    db_gen = get_db()
    db: AsyncSession = await db_gen.__anext__()

    try:
        service = QdrantIngestService()
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
    """Run a similarity search against a Qdrant collection."""
    service = QdrantIngestService()
    results = service.test_similarity_search(
        collection_name=name,
        query_text=query,
        limit=limit,
    )
    return results
```

#### 9.2 Register the router in `src/main.py`

Add to the existing imports and `app` setup:

```python
from src.routers.ingest import router as ingest_router

app.include_router(ingest_router, prefix="/api/v1")
```

---

## Done-When Checklist

| # | Criterion | Verify |
|---|-----------|--------|
| 1 | `QdrantIngestService().ensure_collection("test")` creates a collection in Qdrant | Qdrant dashboard shows collection with 384 dims, cosine distance |
| 2 | `chunk_job_task` and `embed_job_task` registered in Celery worker | Can be invoked via `.delay()` |
| 3 | `POST /api/v1/ingest/jobs/{id}/chunk` → 200 with task_id | Returns `{"task_id": "...", "status": "chunking_started"}` |
| 4 | `GET /api/v1/ingest/jobs/{id}/chunks` → 200 with chunk list | Returns array of ChunkDocument objects |
| 5 | `GET /api/v1/ingest/jobs/{id}/chunks/{chunk_id}` → 200 with single chunk | Returns ChunkDocument |
| 6 | `GET /api/v1/ingest/jobs/{id}/chunk-stats` → 200 with statistics | Returns ChunkStats with histogram |
| 7 | `POST /api/v1/ingest/jobs/{id}/embed` → 200 with task_id | Returns task_id + collection_name |
| 8 | WebSocket `/api/v1/ingest/jobs/{id}/embed/ws` streams progress | EmbedProgress events received |
| 9 | `GET /api/v1/ingest/collections` → 200 with list | Returns CollectionInfo array |
| 10 | `GET /api/v1/ingest/collections/{name}/stats` → 200 | Returns CollectionStats |
| 11 | `POST /api/v1/ingest/collections/{name}/search` → 200 with results | Similarity search returns scored results |
| 12 | Ingest router registered in `main.py` | Router appears in OpenAPI docs |

---

## Summary Report

Upon completion of this subtask, create a summary report at:
`rag-pipeline/ai-workspace/summary-reports/phase-6-subtask-3-qdrant-celery-api-summary.md`

The summary report must include:
- **Subtask**: Phase 6, Subtask 3 — Qdrant Ingestion Service + Celery Tasks + API Router
- **Status**: Complete / Partial / Blocked
- **Date**: {ISO 8601 date}
- **Files Created/Modified**: List every file path
- **Key Decisions**: Any deviations from the plan and why
- **Issues Encountered**: Problems and resolutions
- **Dependencies for Next Subtask**: What the next subtask needs to know
- **Verification Results**: Output of Done-When checklist items
