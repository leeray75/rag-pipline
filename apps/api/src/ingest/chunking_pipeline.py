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
