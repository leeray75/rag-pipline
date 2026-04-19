"""Pydantic schemas for Qdrant collection metadata."""

from datetime import datetime

from pydantic import BaseModel


class CollectionInfo(BaseModel):
    """Collection metadata stored in Postgres and returned by API."""

    id: str
    job_id: str
    collection_name: str
    embedding_model: str
    vector_dimensions: int
    vector_count: int
    document_count: int
    status: str  # "creating" | "ready" | "error"
    created_at: datetime
    updated_at: datetime


class CollectionStats(BaseModel):
    """Live stats queried from Qdrant for a collection."""

    collection_name: str
    vector_count: int
    indexed_vectors: int
    points_count: int
    segments_count: int
    disk_data_size_bytes: int
    ram_data_size_bytes: int
    status: str
