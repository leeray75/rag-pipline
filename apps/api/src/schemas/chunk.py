"""Pydantic schemas for JSON chunk documents."""

from datetime import datetime

from pydantic import BaseModel, Field


class ChunkMetadata(BaseModel):
    """Metadata attached to each chunk for Qdrant payload filtering."""

    source_url: str
    title: str = ""
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    heading_path: str = ""
    fetched_at: datetime | None = None
    approved_at: datetime | None = None
    audit_rounds: int = 0
    quality_score: float = 0.0


class ChunkDocument(BaseModel):
    """The full JSON document stored per chunk — serialized to staging."""

    id: str
    document_id: str
    job_id: str
    chunk_index: int
    total_chunks: int
    content: str
    token_count: int
    metadata: ChunkMetadata

    class Config:
        json_schema_extra = {
            "example": {
                "id": "c1a2b3c4-d5e6-f7a8-b9c0-d1e2f3a4b5c6",
                "document_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "job_id": "j1k2l3m4-n5o6-p7q8-r9s0-t1u2v3w4x5y6",
                "chunk_index": 0,
                "total_chunks": 8,
                "content": "The full text of this chunk...",
                "token_count": 487,
                "metadata": {
                    "source_url": "https://example.com/docs/getting-started",
                    "title": "Getting Started with MCP",
                    "description": "Introduction to the Model Context Protocol",
                    "tags": ["mcp", "protocol", "getting-started"],
                    "heading_path": "Introduction > What is MCP > Core Concepts",
                    "fetched_at": "2025-01-01T00:00:00Z",
                    "approved_at": "2025-01-02T00:00:00Z",
                    "audit_rounds": 2,
                    "quality_score": 94.0,
                },
            }
        }


class ChunkStats(BaseModel):
    """Statistics for a batch of chunks — used by the review UI."""

    job_id: str
    total_chunks: int
    avg_token_count: float
    min_token_count: int
    max_token_count: int
    total_tokens: int
    token_histogram: list[int] = Field(
        default_factory=list,
        description="Bucket counts for token ranges: 0-128, 128-256, 256-384, 384-512, 512-768, 768-1024, 1024+",
    )


class EmbedRequest(BaseModel):
    """Request to embed and ingest chunks for a job."""

    job_id: str
    collection_name: str = Field(
        ...,
        pattern=r"^[a-z][a-z0-9_-]{2,62}$",
        description="Qdrant collection name (lowercase, 3-63 chars, starts with letter)",
    )
    model_name: str = "BAAI/bge-small-en-v1.5"


class EmbedProgress(BaseModel):
    """WebSocket progress update during embedding."""

    job_id: str
    phase: str  # "embedding" | "upserting" | "complete" | "error"
    current: int
    total: int
    message: str
