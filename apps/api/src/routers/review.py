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
