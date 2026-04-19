# Phase 5, Subtask 1 — Frontend Dependencies, Review Data Models & API Endpoints

**Phase**: Phase 5 — Human Review Interface & Approval Workflow
**Subtask**: 1 of 3
**Prerequisites**: Phase 4 complete — Audit-correct loop runs, corrected Markdown files in staging, audit reports stored, A2A messages flowing.
**Scope**: Install frontend editor dependencies, create SQLAlchemy review models with Alembic migration, build Pydantic schemas, and implement all review API endpoints.

---

## Files to Create/Modify

| Action | File Path |
|--------|-----------|
| Modify | `rag-pipeline/apps/web/package.json` (via pnpm add) |
| Create | `rag-pipeline/apps/api/src/models/review.py` |
| Modify | `rag-pipeline/apps/api/src/models/__init__.py` |
| Create | `rag-pipeline/apps/api/alembic/versions/<auto>_add_review_decisions_and_review_comments.py` |
| Create | `rag-pipeline/apps/api/src/schemas/review.py` |
| Create | `rag-pipeline/apps/api/src/routers/review.py` |
| Modify | `rag-pipeline/apps/api/src/main.py` |

---

## Relevant Technology Stack

| Package | Version | Notes |
|---------|---------|-------|
| Python | 3.13.x | Runtime |
| FastAPI | 0.135.3 | `pip install "fastapi[standard]"` |
| Pydantic | 2.13.0 | `pip install pydantic` |
| SQLAlchemy | 2.0.49 | `pip install "sqlalchemy[asyncio]"` |
| Alembic | 1.18.4 | `pip install alembic` |
| structlog | 25.4.0 | `pip install structlog` |
| Next.js | 16.2.3 | Frontend framework |
| React | 19.2.5 | Bundled with Next.js |
| @monaco-editor/react | latest | Monaco editor React wrapper |
| diff | latest | Text diff library |
| react-diff-viewer-continued | latest | Side-by-side diff component |

---

## Step-by-Step Implementation

### Step 1: Install Frontend Dependencies

**Working directory**: `rag-pipeline/apps/web/`

```bash
pnpm add @monaco-editor/react diff react-diff-viewer-continued
pnpm add -D @types/diff
```

Verify the install compiles:

```bash
# Quick check — this import should resolve without errors
echo 'import Editor from "@monaco-editor/react"' > /tmp/check.tsx && echo "OK"
```

### Step 2: Create ReviewDecision & ReviewComment SQLAlchemy Models

**Create file**: `rag-pipeline/apps/api/src/models/review.py`

```python
"""Review models — tracks human review decisions on documents."""

import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDMixin


class ReviewDecision(Base, UUIDMixin, TimestampMixin):
    """A human review decision on a single document."""

    __tablename__ = "review_decisions"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ingestion_jobs.id"), nullable=False
    )
    decision: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # "approved" | "rejected" | "edited"
    reviewer_notes: Mapped[str | None] = mapped_column(Text)
    edited_content: Mapped[str | None] = mapped_column(Text)

    # Relationships
    document: Mapped["Document"] = relationship()
    job: Mapped["IngestionJob"] = relationship()


class ReviewComment(Base, UUIDMixin, TimestampMixin):
    """A comment thread on a document during review."""

    __tablename__ = "review_comments"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False
    )
    line_number: Mapped[int | None] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[str] = mapped_column(String(100), default="reviewer")
    resolved: Mapped[bool] = mapped_column(default=False)
```

### Step 3: Update Models `__init__.py`

**Modify file**: `rag-pipeline/apps/api/src/models/__init__.py`

Add the new imports to the existing file:

```python
from src.models.review import ReviewComment, ReviewDecision

__all__ = [
    # ... existing exports
    "ReviewComment",
    "ReviewDecision",
]
```

### Step 4: Generate and Apply Alembic Migration

**Working directory**: `rag-pipeline/apps/api/`

```bash
alembic revision --autogenerate -m "add review_decisions and review_comments"
alembic upgrade head
```

This creates two tables: `review_decisions` and `review_comments`.

### Step 5: Create Review Pydantic Schemas

**Create file**: `rag-pipeline/apps/api/src/schemas/review.py`

```python
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
```

### Step 6: Build Review API Router

**Create file**: `rag-pipeline/apps/api/src/routers/review.py`

```python
"""API routes for human review workflow."""

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.models import Document, IngestionJob, JobStatus
from src.models.review import ReviewComment, ReviewDecision
from src.schemas.review import (
    BatchApproveRequest,
    ReviewCommentCreate,
    ReviewCommentResponse,
    ReviewDecisionCreate,
    ReviewDecisionResponse,
    ReviewSummary,
)

import structlog

logger = structlog.get_logger()

router = APIRouter()


@router.get("/jobs/{job_id}/review/summary", response_model=ReviewSummary)
async def get_review_summary(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get the review status summary for a job."""
    # Total documents
    total_result = await db.execute(
        select(func.count()).where(Document.job_id == job_id)
    )
    total = total_result.scalar() or 0

    # Count by decision type
    decisions_result = await db.execute(
        select(ReviewDecision.decision, func.count())
        .where(ReviewDecision.job_id == job_id)
        .group_by(ReviewDecision.decision)
    )
    decision_counts = dict(decisions_result.all())

    approved = decision_counts.get("approved", 0)
    rejected = decision_counts.get("rejected", 0)
    edited = decision_counts.get("edited", 0)
    pending = total - approved - rejected - edited

    return ReviewSummary(
        total_documents=total,
        approved=approved,
        rejected=rejected,
        edited=edited,
        pending=pending,
        all_reviewed=pending == 0,
    )


@router.get("/jobs/{job_id}/review/documents")
async def list_review_documents(
    job_id: uuid.UUID,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """List documents for review with their current review status."""
    query = select(Document).where(Document.job_id == job_id).order_by(Document.created_at)
    result = await db.execute(query)
    documents = result.scalars().all()

    # Get existing decisions
    decisions = await db.execute(
        select(ReviewDecision).where(ReviewDecision.job_id == job_id)
    )
    decision_map = {str(d.document_id): d for d in decisions.scalars().all()}

    items = []
    for doc in documents:
        decision = decision_map.get(str(doc.id))
        review_status = decision.decision if decision else "pending"

        if status and review_status != status:
            continue

        items.append({
            "id": str(doc.id),
            "url": doc.url,
            "title": doc.title,
            "word_count": doc.word_count,
            "quality_score": doc.quality_score,
            "review_status": review_status,
            "reviewer_notes": decision.reviewer_notes if decision else None,
        })

    return items


@router.get("/jobs/{job_id}/review/documents/{doc_id}")
async def get_review_document(
    job_id: uuid.UUID, doc_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    """Get full document content for review with diff data."""
    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.job_id == job_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Read current Markdown
    markdown = ""
    if doc.markdown_path:
        md_path = Path(doc.markdown_path)
        if md_path.exists():
            markdown = md_path.read_text(encoding="utf-8")

    # Read original (round 1 backup if exists)
    original = markdown
    if doc.markdown_path:
        backup_path = Path(doc.markdown_path).with_suffix(".round1.bak.md")
        if backup_path.exists():
            original = backup_path.read_text(encoding="utf-8")

    # Get review decision if exists
    dec_result = await db.execute(
        select(ReviewDecision).where(
            ReviewDecision.document_id == doc_id,
            ReviewDecision.job_id == job_id,
        )
    )
    decision = dec_result.scalar_one_or_none()

    # Get comments
    comments_result = await db.execute(
        select(ReviewComment)
        .where(ReviewComment.document_id == doc_id)
        .order_by(ReviewComment.created_at)
    )
    comments = comments_result.scalars().all()

    return {
        "id": str(doc.id),
        "url": doc.url,
        "title": doc.title,
        "word_count": doc.word_count,
        "quality_score": doc.quality_score,
        "current_markdown": markdown,
        "original_markdown": original,
        "has_changes": markdown != original,
        "review_decision": {
            "decision": decision.decision,
            "reviewer_notes": decision.reviewer_notes,
            "created_at": decision.created_at.isoformat(),
        } if decision else None,
        "comments": [
            {
                "id": str(c.id),
                "line_number": c.line_number,
                "content": c.content,
                "author": c.author,
                "resolved": c.resolved,
                "created_at": c.created_at.isoformat(),
            }
            for c in comments
        ],
    }


@router.post("/jobs/{job_id}/review/documents/{doc_id}/decide")
async def submit_review_decision(
    job_id: uuid.UUID,
    doc_id: uuid.UUID,
    payload: ReviewDecisionCreate,
    db: AsyncSession = Depends(get_db),
):
    """Submit a review decision (approve/reject/edit) for a document."""
    # Validate document exists
    doc_result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.job_id == job_id)
    )
    doc = doc_result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if payload.decision not in ("approved", "rejected", "edited"):
        raise HTTPException(status_code=400, detail="Decision must be: approved, rejected, or edited")

    # Upsert decision (overwrite if exists)
    existing = await db.execute(
        select(ReviewDecision).where(
            ReviewDecision.document_id == doc_id,
            ReviewDecision.job_id == job_id,
        )
    )
    decision = existing.scalar_one_or_none()

    if decision:
        decision.decision = payload.decision
        decision.reviewer_notes = payload.reviewer_notes
        decision.edited_content = payload.edited_content
    else:
        decision = ReviewDecision(
            document_id=doc_id,
            job_id=job_id,
            decision=payload.decision,
            reviewer_notes=payload.reviewer_notes,
            edited_content=payload.edited_content,
        )
        db.add(decision)

    # If edited, write the new content to the Markdown file
    if payload.decision == "edited" and payload.edited_content and doc.markdown_path:
        md_path = Path(doc.markdown_path)
        if md_path.exists():
            # Backup current version
            backup = md_path.with_suffix(".pre-edit.bak.md")
            backup.write_text(md_path.read_text(encoding="utf-8"), encoding="utf-8")
            # Write edited content
            md_path.write_text(payload.edited_content, encoding="utf-8")

    await db.commit()

    logger.info("review_decision", doc_id=str(doc_id), decision=payload.decision)
    return {"status": "ok", "decision": payload.decision}


@router.post("/jobs/{job_id}/review/batch-approve")
async def batch_approve(
    job_id: uuid.UUID,
    payload: BatchApproveRequest,
    db: AsyncSession = Depends(get_db),
):
    """Batch approve multiple documents at once."""
    approved_count = 0

    for doc_id in payload.document_ids:
        existing = await db.execute(
            select(ReviewDecision).where(
                ReviewDecision.document_id == doc_id,
                ReviewDecision.job_id == job_id,
            )
        )
        decision = existing.scalar_one_or_none()

        if decision:
            decision.decision = "approved"
            decision.reviewer_notes = payload.reviewer_notes
        else:
            db.add(ReviewDecision(
                document_id=doc_id,
                job_id=job_id,
                decision="approved",
                reviewer_notes=payload.reviewer_notes,
            ))
        approved_count += 1

    await db.commit()
    return {"approved_count": approved_count}


@router.post("/jobs/{job_id}/review/finalize")
async def finalize_review(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Finalize review — transition job to next pipeline stage.

    Requires all documents to be reviewed (no pending).
    """
    job_result = await db.execute(select(IngestionJob).where(IngestionJob.id == job_id))
    job = job_result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Check all documents are reviewed
    total_result = await db.execute(
        select(func.count()).where(Document.job_id == job_id)
    )
    total = total_result.scalar() or 0

    reviewed_result = await db.execute(
        select(func.count()).where(ReviewDecision.job_id == job_id)
    )
    reviewed = reviewed_result.scalar() or 0

    if reviewed < total:
        raise HTTPException(
            status_code=400,
            detail=f"Not all documents reviewed: {reviewed}/{total}. Review remaining documents first."
        )

    # Check for any rejected documents
    rejected_result = await db.execute(
        select(func.count()).where(
            ReviewDecision.job_id == job_id,
            ReviewDecision.decision == "rejected",
        )
    )
    rejected_count = rejected_result.scalar() or 0

    # Transition job
    job.status = JobStatus.APPROVED
    await db.commit()

    logger.info(
        "review_finalized",
        job_id=str(job_id),
        total=total,
        approved=total - rejected_count,
        rejected=rejected_count,
    )

    return {
        "status": "finalized",
        "total_documents": total,
        "approved": total - rejected_count,
        "rejected": rejected_count,
        "next_step": "JSON generation and vector ingestion",
    }


# --- Comments ---
@router.post("/jobs/{job_id}/review/documents/{doc_id}/comments")
async def add_comment(
    job_id: uuid.UUID,
    doc_id: uuid.UUID,
    payload: ReviewCommentCreate,
    db: AsyncSession = Depends(get_db),
):
    """Add a comment to a document."""
    comment = ReviewComment(
        document_id=doc_id,
        line_number=payload.line_number,
        content=payload.content,
    )
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    return {"id": str(comment.id), "status": "created"}


@router.patch("/jobs/{job_id}/review/comments/{comment_id}/resolve")
async def resolve_comment(
    job_id: uuid.UUID,
    comment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Mark a comment as resolved."""
    result = await db.execute(select(ReviewComment).where(ReviewComment.id == comment_id))
    comment = result.scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    comment.resolved = True
    await db.commit()
    return {"status": "resolved"}
```

### Step 7: Register Router in Main App

**Modify file**: `rag-pipeline/apps/api/src/main.py`

Add the review router import and registration alongside existing routers:

```python
from src.routers import health, jobs, websocket, audit, loop, review

app.include_router(review.router, prefix="/api/v1", tags=["review"])
```

---

## Done-When Checklist

- [ ] `review_decisions` and `review_comments` tables created via Alembic migration
- [ ] `GET /api/v1/jobs/{id}/review/summary` returns counts for approved/rejected/edited/pending
- [ ] `GET /api/v1/jobs/{id}/review/documents` returns document list with review status
- [ ] `GET /api/v1/jobs/{id}/review/documents/{docId}` returns full content + original diff data
- [ ] `POST .../decide` accepts `approved`, `rejected`, `edited` decisions
- [ ] `edited` decision writes modified content back to the Markdown file
- [ ] `POST .../batch-approve` approves multiple documents in one call
- [ ] `POST .../finalize` transitions job to `APPROVED` status — blocks if pending remain
- [ ] `POST .../comments` creates a comment on a document
- [ ] `PATCH .../comments/{id}/resolve` marks a comment as resolved
- [ ] `import Editor from "@monaco-editor/react"` compiles without errors in the web app
- [ ] `python -c "from src.schemas.review import ReviewDecisionCreate"` succeeds

---

## Summary Report

Upon completion of this subtask, create a summary report at:
`rag-pipeline/ai-workspace/summary-reports/phase-5-subtask-1-models-api-and-deps-summary.md`

The summary report must include:
- **Subtask**: Phase 5, Subtask 1 — Frontend Dependencies, Review Data Models & API Endpoints
- **Status**: Complete / Partial / Blocked
- **Date**: {ISO 8601 date}
- **Files Created/Modified**: List every file path
- **Key Decisions**: Any deviations from the plan and why
- **Issues Encountered**: Problems and resolutions
- **Dependencies for Next Subtask**: What the next subtask needs to know
- **Verification Results**: Output of Done-When checklist items
