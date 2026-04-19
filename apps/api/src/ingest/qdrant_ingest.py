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

from src.config import settings
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
