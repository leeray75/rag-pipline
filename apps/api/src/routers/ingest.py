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
