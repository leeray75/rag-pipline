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
