"""Pydantic schemas for documents."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class DocumentResponse(BaseModel):
    """Schema for document API responses."""

    id: uuid.UUID
    job_id: uuid.UUID
    url: str
    title: str | None
    status: str
    word_count: int | None
    quality_score: int | None
    created_at: datetime

    model_config = {"from_attributes": True}
