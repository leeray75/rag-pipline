# Phase 6, Subtask 5 — Ingest Page + Environment Variables + Tests + Phase Validation

> **Phase**: Phase 6 — JSON Generation, Chunking & Vector Ingestion
> **Prerequisites**: Phase 5 complete + Phase 6 Subtasks 1–4 complete (all backend services, API router, Celery tasks, RTK Query, ChunkBrowser, EmbedToQdrant components working)
> **Subtask Scope**: Tasks 13–15 from Phase 6 (Ingest page route, environment variables, Docker Compose updates, test suite, Done-When validation)

---

## Files to Create / Modify

| Action | File Path |
|--------|-----------|
| Create | `rag-pipeline/apps/web/src/app/jobs/[jobId]/ingest/page.tsx` |
| Modify | `rag-pipeline/apps/api/.env.example` |
| Modify | `rag-pipeline/infra/docker-compose.yml` |
| Create | `rag-pipeline/apps/api/tests/test_chunker.py` |
| Create | `rag-pipeline/apps/api/tests/test_fastembed_service.py` |

---

## Relevant Technology Stack

| Package | Version | Notes |
|---------|---------|-------|
| Next.js | 16.2.3 | App Router page |
| Python | 3.13.x | Test runtime |
| pytest | latest | Test framework |
| fastembed | 0.8.0 | Tested in test_fastembed_service.py |
| tiktoken | 0.12.0 | Used by chunker under test |
| qdrant-client | 1.17.1 | Qdrant Docker service |
| Docker Compose | 2.x | Infrastructure config |

---

## Step-by-Step Implementation

### Task 13: Create the Ingest Page

**Working directory**: `rag-pipeline/apps/web/`

#### 13.1 Create `src/app/jobs/[jobId]/ingest/page.tsx`

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

---

### Task 14: Add Environment Variables

#### 14.1 Update `rag-pipeline/apps/api/.env.example`

Append these lines to the existing `.env.example`:

```env
# --- Phase 6: Embedding & Ingestion ---
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
EMBEDDING_BATCH_SIZE=100
FASTEMBED_CACHE_DIR=
FASTEMBED_THREADS=
QDRANT_URL=http://localhost:6333
```

#### 14.2 Update Docker Compose

In `rag-pipeline/infra/docker-compose.yml`, ensure the API service has the embedding environment variables and the Qdrant service is properly configured:

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

> **Note**: The Qdrant service should already exist from Phase 1. Only add the `api` environment variables if not already present. The `QDRANT_URL` inside Docker uses the service name `qdrant` instead of `localhost`.

---

### Task 15: Write Tests

**Working directory**: `rag-pipeline/apps/api/`

#### 15.1 Create `tests/test_chunker.py`

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

#### 15.2 Create `tests/test_fastembed_service.py`

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

#### 15.3 Run tests

```bash
cd rag-pipeline/apps/api && python -m pytest tests/test_chunker.py tests/test_fastembed_service.py -v
```

---

## Full Phase 6 Done-When Checklist

This is the complete validation checklist for the entire Phase 6. All items from Subtasks 1–5 must pass.

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

### Run Full Validation

```bash
# Run all Phase 6 tests
cd rag-pipeline/apps/api && python -m pytest tests/test_chunker.py tests/test_fastembed_service.py -v

# Verify API endpoints (with server running)
curl -X POST http://localhost:8000/api/v1/ingest/jobs/test-job/chunk
curl http://localhost:8000/api/v1/ingest/collections

# Run phase validation script if available
bash rag-pipeline/ai-workspace/plans/phase-6/validation.sh
```

---

## Summary Report

Upon completion of this subtask, create a summary report at:
`rag-pipeline/ai-workspace/summary-reports/phase-6-subtask-5-ingest-page-env-tests-validation-summary.md`

The summary report must include:
- **Subtask**: Phase 6, Subtask 5 — Ingest Page + Environment Variables + Tests + Phase Validation
- **Status**: Complete / Partial / Blocked
- **Date**: {ISO 8601 date}
- **Files Created/Modified**: List every file path
- **Key Decisions**: Any deviations from the plan and why
- **Issues Encountered**: Problems and resolutions
- **Dependencies for Next Subtask**: What the next subtask needs to know (Phase 7 prerequisites)
- **Verification Results**: Output of Done-When checklist items
