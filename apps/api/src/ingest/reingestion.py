"""Re-ingestion service — detect updated docs and trigger delta pipeline.

Compares fetched content hashes to detect changes since last ingestion.
Only re-processes documents whose content has actually changed.
"""

import hashlib
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.document import Document
from src.models.chunk import ChunkRecord

logger = logging.getLogger(__name__)


class ReingestionService:
    """Detects changes in source documentation and triggers re-processing."""

    @staticmethod
    def content_hash(content: str) -> str:
        """SHA-256 hash of document content."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    async def detect_changes(
        self,
        *,
        job_id: str,
        new_documents: list[dict],
        db: AsyncSession,
    ) -> dict:
        """Compare new document content against stored hashes.

        Parameters
        ----------
        job_id : str
            The original job ID to compare against.
        new_documents : list[dict]
            Each dict: {source_url, content, title}.
        db : AsyncSession
            Database session.

        Returns
        -------
        dict with keys: added, updated, unchanged, removed
        """
        # Load existing documents for this job
        stmt = select(Document).where(Document.job_id == job_id)
        result = await db.execute(stmt)
        existing = {d.source_url: d for d in result.scalars().all()}

        new_urls = {d["source_url"] for d in new_documents}
        existing_urls = set(existing.keys())

        added = []
        updated = []
        unchanged = []
        removed = list(existing_urls - new_urls)

        for doc_data in new_documents:
            url = doc_data["source_url"]
            new_hash = self.content_hash(doc_data["content"])

            if url not in existing:
                added.append(url)
            elif existing[url].content_hash != new_hash:
                updated.append(url)
            else:
                unchanged.append(url)

        logger.info(
            "Re-ingestion delta: added=%d updated=%d unchanged=%d removed=%d",
            len(added),
            len(updated),
            len(unchanged),
            len(removed),
        )

        return {
            "added": added,
            "updated": updated,
            "unchanged": unchanged,
            "removed": removed,
        }

    async def invalidate_chunks(
        self,
        *,
        document_ids: list[str],
        db: AsyncSession,
    ) -> int:
        """Delete chunks for documents that need re-processing.

        Returns the number of chunks deleted.
        """
        from sqlalchemy import delete

        stmt = delete(ChunkRecord).where(
            ChunkRecord.document_id.in_(document_ids)
        )
        result = await db.execute(stmt)
        await db.commit()
        deleted = result.rowcount
        logger.info("Invalidated %d chunks for %d documents", deleted, len(document_ids))
        return deleted
