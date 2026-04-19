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
    from sqlalchemy import select

    from src.database import async_session_factory
    from src.ingest.chunking_pipeline import ChunkingPipeline
    from src.models.document import Document

    logger.info("Starting chunking task for job %s", job_id)

    async def _run() -> dict:
        async with async_session_factory() as db:
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
                approved.append(
                    {
                        "document_id": str(doc.id),
                        "markdown_content": markdown_content,
                        "source_url": doc.url or "",
                        "title": doc.title or "",
                        "description": "",
                        "tags": [],
                        "fetched_at": str(doc.created_at) if doc.created_at else None,
                        "approved_at": str(doc.updated_at) if doc.updated_at else None,
                        "audit_rounds": 0,
                        "quality_score": 0.0,
                    }
                )

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
    from sqlalchemy import select

    from src.database import async_session_factory
    from src.ingest.qdrant_ingest import QdrantIngestService
    from src.models.chunk import ChunkRecord

    logger.info(
        "Starting embed task for job %s -> collection '%s'",
        job_id,
        collection_name,
    )

    async def _run() -> dict:
        service = QdrantIngestService()
        async with async_session_factory() as db:
            # Ensure collection exists first
            service.ensure_collection(collection_name)

            # Load pending chunks
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
                return {
                    "job_id": job_id,
                    "phase": "complete",
                    "current": 0,
                    "total": 0,
                    "message": "No pending chunks to embed",
                }

            # Embed in batches
            batch_size = service.embed_config.batch_size
            all_embeddings: list = []
            for start in range(0, total, batch_size):
                end = min(start + batch_size, total)
                batch_texts = [c.content for c in chunks[start:end]]
                batch_embeddings = service._embed_with_retry(batch_texts, max_retries=3)
                all_embeddings.extend(batch_embeddings)

            # Upsert to Qdrant
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
                        {
                            "id": str(chunk.id),
                            "vector": embedding.tolist(),
                            "payload": payload,
                        }
                    )

                service.qdrant.upsert(
                    collection_name=collection_name,
                    points=points,
                )

                # Mark chunks as embedded
                for i in range(start, end):
                    chunks[i].embedding_status = "embedded"

            # Record collection in Postgres
            collection_record = ChunkRecord.__table__.c  # type: ignore
            from src.models.chunk import VectorCollection

            collection = VectorCollection(
                job_id=job_id,
                collection_name=collection_name,
                embedding_model=service.embed_config.model_name,
                vector_dimensions=service.embed_config.dimensions,
                vector_count=total,
                document_count=len(set(str(c.document_id) for c in chunks)),
                status="ready",
            )
            db.add(collection)
            await db.commit()

            return {
                "job_id": job_id,
                "phase": "complete",
                "current": total,
                "total": total,
                "message": f"Ingestion complete: {total} vectors in '{collection_name}'",
            }

    return asyncio.run(_run())
