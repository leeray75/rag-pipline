# Phase 6, Subtask 1 — Dependencies + Chunking Engine + Embedding Service

> **Phase**: Phase 6 — JSON Generation, Chunking & Vector Ingestion
> **Prerequisites**: Phase 5 complete — Human review dashboard working, approve/reject/edit workflow functional, approved documents in staging with `status = "approved"`.
> **Subtask Scope**: Tasks 1–3 from Phase 6 (Python deps, MarkdownChunker, FastEmbedService)

---

## Files to Create / Modify

| Action | File Path |
|--------|-----------|
| Modify | `rag-pipeline/apps/api/pyproject.toml` |
| Create | `rag-pipeline/apps/api/src/ingest/__init__.py` |
| Create | `rag-pipeline/apps/api/src/ingest/chunker.py` |
| Create | `rag-pipeline/apps/api/src/embeddings/__init__.py` |
| Create | `rag-pipeline/apps/api/src/embeddings/fastembed_service.py` |
| Create | `rag-pipeline/apps/api/src/embeddings/config.py` |

---

## Relevant Technology Stack

| Package | Version | Install |
|---------|---------|---------|
| Python | 3.13.x | Runtime |
| FastAPI | 0.135.3 | already installed |
| fastembed | 0.8.0 | `pip install fastembed` |
| tiktoken | 0.12.0 | `pip install tiktoken` |

### Embedding Model Details

| Model | Identifier | Dimensions | Max Tokens | Size |
|-------|-----------|------------|------------|------|
| BGE-small-en-v1.5 (primary) | `BAAI/bge-small-en-v1.5` | 384 | 512 | ~33M params |
| GTE-small (alternative) | `thenlper/gte-small` | 384 | 512 | ~33M params |

> **Why FastEmbed?** Runs locally with ONNX Runtime — no external API calls, no API keys, no rate limits, deterministic embeddings, fast batch processing. Both models produce 384-dimension vectors with cosine similarity.

---

## Step-by-Step Implementation

### Task 1: Add Phase 6 Python Dependencies

**Working directory**: `rag-pipeline/apps/api/`

#### 1.1 Update `pyproject.toml` — add to `[project.dependencies]`

```toml
[project.dependencies]
# ... existing deps from Phase 1-5 ...
fastembed = ">=0.8.0,<1.0.0"
tiktoken = ">=0.12.0,<1.0.0"
```

#### 1.2 Install and verify

```bash
cd rag-pipeline/apps/api && pip install -e ".[dev]"
```

#### 1.3 Verify FastEmbed loads the model

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

---

### Task 2: Create the Chunking Engine

**Working directory**: `rag-pipeline/apps/api/`

#### 2.1 Create `src/ingest/chunker.py`

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

#### 2.2 Create `src/ingest/__init__.py`

```python
"""Ingest package — chunking, embedding, and vector store operations."""
```

---

### Task 3: Create the Embedding Service (FastEmbed)

**Working directory**: `rag-pipeline/apps/api/`

#### 3.1 Create `src/embeddings/__init__.py`

```python
"""Embeddings package — FastEmbed model wrappers."""
```

#### 3.2 Create `src/embeddings/fastembed_service.py`

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

#### 3.3 Create `src/embeddings/config.py`

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

---

## Done-When Checklist

| # | Criterion | Verify |
|---|-----------|--------|
| 1 | `fastembed` 0.8.0 and `tiktoken` 0.12.0 installed | `pip install -e ".[dev]"` succeeds |
| 2 | `BAAI/bge-small-en-v1.5` loads and produces 384-dim vectors | `python -c "from fastembed import TextEmbedding; m = TextEmbedding('BAAI/bge-small-en-v1.5'); print(len(list(m.embed(['test']))[0]))"` → 384 |
| 3 | `from src.ingest.chunker import MarkdownChunker, Chunk` imports successfully | Python import check |
| 4 | `MarkdownChunker` splits docs with heading-path tracking | Manual test with multi-heading Markdown |
| 5 | `from src.embeddings.fastembed_service import FastEmbedService` works | Python import check |
| 6 | `FastEmbedService().embed_single("test")` returns a 384-dim `numpy.ndarray` | Manual verification |

---

## Summary Report

Upon completion of this subtask, create a summary report at:
`rag-pipeline/ai-workspace/summary-reports/phase-6-subtask-1-deps-chunking-embedding-summary.md`

The summary report must include:
- **Subtask**: Phase 6, Subtask 1 — Dependencies + Chunking Engine + Embedding Service
- **Status**: Complete / Partial / Blocked
- **Date**: {ISO 8601 date}
- **Files Created/Modified**: List every file path
- **Key Decisions**: Any deviations from the plan and why
- **Issues Encountered**: Problems and resolutions
- **Dependencies for Next Subtask**: What the next subtask needs to know
- **Verification Results**: Output of Done-When checklist items
