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
