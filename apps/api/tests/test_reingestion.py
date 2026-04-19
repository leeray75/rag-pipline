"""Tests for re-ingestion delta detection."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.ingest.reingestion import ReingestionService


def test_content_hash_is_deterministic():
    """Same content always produces the same hash."""
    svc = ReingestionService()
    h1 = svc.content_hash("hello world")
    h2 = svc.content_hash("hello world")
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex = 64 chars


def test_content_hash_differs_for_different_content():
    """Different content produces different hashes."""
    svc = ReingestionService()
    h1 = svc.content_hash("version 1")
    h2 = svc.content_hash("version 2")
    assert h1 != h2


@pytest.mark.asyncio
async def test_detect_changes_identifies_added():
    """New URLs not in DB are classified as added."""
    svc = ReingestionService()

    # Mock DB session returning no existing documents
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_result

    new_docs = [{"source_url": "https://example.com/new", "content": "new content"}]
    delta = await svc.detect_changes(job_id="job-1", new_documents=new_docs, db=mock_db)

    assert "https://example.com/new" in delta["added"]
    assert len(delta["updated"]) == 0
    assert len(delta["unchanged"]) == 0


@pytest.mark.asyncio
async def test_detect_changes_identifies_unchanged():
    """URLs with same hash are classified as unchanged."""
    svc = ReingestionService()
    content = "same content"
    existing_hash = svc.content_hash(content)

    # Mock existing document with same hash
    mock_doc = MagicMock()
    mock_doc.source_url = "https://example.com/page"
    mock_doc.content_hash = existing_hash

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_doc]
    mock_db.execute.return_value = mock_result

    new_docs = [{"source_url": "https://example.com/page", "content": content}]
    delta = await svc.detect_changes(job_id="job-1", new_documents=new_docs, db=mock_db)

    assert "https://example.com/page" in delta["unchanged"]
    assert len(delta["updated"]) == 0
    assert len(delta["added"]) == 0
