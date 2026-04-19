"""Pydantic schemas for human review."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class ReviewDecisionCreate(BaseModel):
    """Schema for submitting a review decision."""

    decision: str  # "approved" | "rejected" | "edited"
    reviewer_notes: str | None = None
    edited_content: str | None = None


class ReviewDecisionResponse(BaseModel):
    """Schema for review decision API response."""

    id: uuid.UUID
    document_id: uuid.UUID
    job_id: uuid.UUID
    decision: str
    reviewer_notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ReviewCommentCreate(BaseModel):
    """Schema for creating a review comment."""

    line_number: int | None = None
    content: str


class ReviewCommentResponse(BaseModel):
    """Schema for review comment API response."""

    id: uuid.UUID
    document_id: uuid.UUID
    line_number: int | None
    content: str
    author: str
    resolved: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class BatchApproveRequest(BaseModel):
    """Schema for batch-approving multiple documents."""

    document_ids: list[uuid.UUID]
    reviewer_notes: str | None = None


class ReviewSummary(BaseModel):
    """Summary of review status for a job."""

    total_documents: int
    approved: int
    rejected: int
    edited: int
    pending: int
    all_reviewed: bool
