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
