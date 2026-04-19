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
