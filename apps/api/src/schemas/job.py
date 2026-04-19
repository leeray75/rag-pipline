"""Pydantic schemas for ingestion jobs."""

import uuid
from datetime import datetime

from pydantic import BaseModel, HttpUrl


class JobCreate(BaseModel):
    """Schema for creating a new ingestion job."""

    url: HttpUrl
    crawl_all_docs: bool = False


class JobResponse(BaseModel):
    """Schema for job API responses."""

    id: uuid.UUID
    url: str
    status: str
    crawl_all_docs: bool
    total_documents: int
    processed_documents: int
    current_audit_round: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JobStatusResponse(BaseModel):
    """Lightweight job status for polling."""

    id: uuid.UUID
    status: str
    total_documents: int
    processed_documents: int
    current_audit_round: int
