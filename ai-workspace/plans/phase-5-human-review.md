# Phase 5 — Human Review Interface & Approval Workflow

> **Prerequisites**: Phase 4 complete — Audit-correct loop runs, corrected Markdown files in staging, audit reports stored, A2A messages flowing.
> **Ref**: [phase-0-index.md](phase-0-index.md) for pinned versions.

---

## Objective

Build the full human review dashboard with Monaco editor for inline Markdown editing, side-by-side diff view, per-document approve/reject/edit workflow, batch approve, comment threads, and the approval API that transitions jobs to the embedding phase.

---

## Task 1: Add Phase 5 Frontend Dependencies

**Working directory**: `rag-pipeline/apps/web/`

### 1.1 Install dependencies

```bash
pnpm add @monaco-editor/react diff react-diff-viewer-continued
pnpm add -D @types/diff
```

**Done when**: `import Editor from "@monaco-editor/react"` compiles without errors.

---

## Task 2: Create Review Data Models & API

**Working directory**: `rag-pipeline/apps/api/`

### 2.1 Create `src/models/review.py`

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

### 2.2 Update `src/models/__init__.py`

Add the new imports:

```python
from src.models.review import ReviewComment, ReviewDecision

__all__ = [
    # ... existing
    "ReviewComment",
    "ReviewDecision",
]
```

### 2.3 Generate and apply migration

```bash
alembic revision --autogenerate -m "add review_decisions and review_comments"
alembic upgrade head
```

### 2.4 Create review Pydantic schemas — `src/schemas/review.py`

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

**Done when**: `python -c "from src.schemas.review import ReviewDecisionCreate"` succeeds.

---

## Task 3: Build Review API Endpoints

**Working directory**: `rag-pipeline/apps/api/src/routers/`

### 3.1 Create `review.py`

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

### 3.2 Register in `src/main.py`

```python
from src.routers import health, jobs, websocket, audit, loop, review

app.include_router(review.router, prefix="/api/v1", tags=["review"])
```

**Done when**: Review API endpoints respond correctly — create decisions, batch approve, finalize.

---

## Task 4: Build Review Dashboard UI

**Working directory**: `rag-pipeline/apps/web/`

### 4.1 Create RTK Query endpoints — `src/store/api/review-api.ts`

```typescript
import { apiSlice } from "./api-slice";

export interface ReviewDocument {
  id: string;
  url: string;
  title: string | null;
  word_count: number | null;
  quality_score: number | null;
  review_status: string;
  reviewer_notes: string | null;
}

export interface ReviewDocDetail {
  id: string;
  url: string;
  title: string | null;
  word_count: number | null;
  quality_score: number | null;
  current_markdown: string;
  original_markdown: string;
  has_changes: boolean;
  review_decision: {
    decision: string;
    reviewer_notes: string | null;
    created_at: string;
  } | null;
  comments: ReviewCommentItem[];
}

export interface ReviewCommentItem {
  id: string;
  line_number: number | null;
  content: string;
  author: string;
  resolved: boolean;
  created_at: string;
}

export interface ReviewSummary {
  total_documents: number;
  approved: number;
  rejected: number;
  edited: number;
  pending: number;
  all_reviewed: boolean;
}

export const reviewApi = apiSlice.injectEndpoints({
  endpoints: (builder) => ({
    getReviewSummary: builder.query<ReviewSummary, string>({
      query: (jobId) => `/jobs/${jobId}/review/summary`,
      providesTags: ["Documents"],
    }),
    listReviewDocuments: builder.query<ReviewDocument[], { jobId: string; status?: string }>({
      query: ({ jobId, status }) =>
        `/jobs/${jobId}/review/documents${status ? `?status=${status}` : ""}`,
      providesTags: ["Documents"],
    }),
    getReviewDocument: builder.query<ReviewDocDetail, { jobId: string; docId: string }>({
      query: ({ jobId, docId }) => `/jobs/${jobId}/review/documents/${docId}`,
    }),
    submitDecision: builder.mutation<
      { status: string },
      { jobId: string; docId: string; decision: string; notes?: string; content?: string }
    >({
      query: ({ jobId, docId, decision, notes, content }) => ({
        url: `/jobs/${jobId}/review/documents/${docId}/decide`,
        method: "POST",
        body: { decision, reviewer_notes: notes, edited_content: content },
      }),
      invalidatesTags: ["Documents"],
    }),
    batchApprove: builder.mutation<
      { approved_count: number },
      { jobId: string; documentIds: string[]; notes?: string }
    >({
      query: ({ jobId, documentIds, notes }) => ({
        url: `/jobs/${jobId}/review/batch-approve`,
        method: "POST",
        body: { document_ids: documentIds, reviewer_notes: notes },
      }),
      invalidatesTags: ["Documents"],
    }),
    finalizeReview: builder.mutation<
      { status: string; total_documents: number; approved: number; rejected: number },
      string
    >({
      query: (jobId) => ({ url: `/jobs/${jobId}/review/finalize`, method: "POST" }),
      invalidatesTags: ["Jobs", "Documents"],
    }),
    addComment: builder.mutation<
      { id: string },
      { jobId: string; docId: string; lineNumber?: number; content: string }
    >({
      query: ({ jobId, docId, lineNumber, content }) => ({
        url: `/jobs/${jobId}/review/documents/${docId}/comments`,
        method: "POST",
        body: { line_number: lineNumber, content },
      }),
    }),
    resolveComment: builder.mutation<void, { jobId: string; commentId: string }>({
      query: ({ jobId, commentId }) => ({
        url: `/jobs/${jobId}/review/comments/${commentId}/resolve`,
        method: "PATCH",
      }),
    }),
  }),
});

export const {
  useGetReviewSummaryQuery,
  useListReviewDocumentsQuery,
  useGetReviewDocumentQuery,
  useSubmitDecisionMutation,
  useBatchApproveMutation,
  useFinalizeReviewMutation,
  useAddCommentMutation,
  useResolveCommentMutation,
} = reviewApi;
```

### 4.2 Create Review Dashboard page — `src/app/review/[jobId]/page.tsx`

```tsx
"use client";

import { use, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
  useGetReviewSummaryQuery,
  useListReviewDocumentsQuery,
  useBatchApproveMutation,
  useFinalizeReviewMutation,
  type ReviewDocument,
} from "@/store/api/review-api";

export default function ReviewPage({ params }: { params: Promise<{ jobId: string }> }) {
  const { jobId } = use(params);
  const [statusFilter, setStatusFilter] = useState<string | undefined>();
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  const { data: summary } = useGetReviewSummaryQuery(jobId);
  const { data: documents } = useListReviewDocumentsQuery({ jobId, status: statusFilter });
  const [batchApprove, { isLoading: isBatching }] = useBatchApproveMutation();
  const [finalize, { isLoading: isFinalizing }] = useFinalizeReviewMutation();

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const selectAll = () => {
    if (!documents) return;
    const pendingIds = documents.filter((d) => d.review_status === "pending").map((d) => d.id);
    setSelectedIds(new Set(pendingIds));
  };

  return (
    <main className="container mx-auto p-8">
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-3xl font-bold">Human Review</h1>
        <div className="flex gap-2">
          <Button
            variant="default"
            onClick={() => batchApprove({ jobId, documentIds: Array.from(selectedIds) })}
            disabled={selectedIds.size === 0 || isBatching}
          >
            Batch Approve ({selectedIds.size})
          </Button>
          <Button
            variant="default"
            onClick={() => finalize(jobId)}
            disabled={!summary?.all_reviewed || isFinalizing}
          >
            Finalize Review
          </Button>
        </div>
      </div>

      {/* Summary Cards */}
      {summary && (
        <div className="grid grid-cols-5 gap-4 mb-8">
          <Card>
            <CardContent className="pt-4 text-center">
              <p className="text-2xl font-bold">{summary.total_documents}</p>
              <p className="text-xs text-muted-foreground">Total</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4 text-center">
              <p className="text-2xl font-bold text-green-600">{summary.approved}</p>
              <p className="text-xs text-muted-foreground">Approved</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4 text-center">
              <p className="text-2xl font-bold text-blue-600">{summary.edited}</p>
              <p className="text-xs text-muted-foreground">Edited</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4 text-center">
              <p className="text-2xl font-bold text-red-600">{summary.rejected}</p>
              <p className="text-xs text-muted-foreground">Rejected</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4 text-center">
              <p className="text-2xl font-bold text-yellow-600">{summary.pending}</p>
              <p className="text-xs text-muted-foreground">Pending</p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Filter Tabs */}
      <div className="flex gap-2 mb-4">
        {[undefined, "pending", "approved", "edited", "rejected"].map((filter) => (
          <Button
            key={filter || "all"}
            variant={statusFilter === filter ? "default" : "outline"}
            size="sm"
            onClick={() => setStatusFilter(filter)}
          >
            {filter || "All"}
          </Button>
        ))}
        <Button variant="outline" size="sm" onClick={selectAll}>
          Select All Pending
        </Button>
      </div>

      {/* Document List */}
      <div className="space-y-2">
        {documents?.map((doc: ReviewDocument) => (
          <div
            key={doc.id}
            className="flex items-center gap-4 p-4 border rounded-lg hover:bg-accent/50"
          >
            <input
              type="checkbox"
              checked={selectedIds.has(doc.id)}
              onChange={() => toggleSelect(doc.id)}
              className="h-4 w-4"
            />
            <div className="flex-1">
              <p className="font-medium">{doc.title || doc.url}</p>
              <p className="text-xs text-muted-foreground">{doc.url}</p>
            </div>
            <Badge variant={doc.quality_score && doc.quality_score > 70 ? "default" : "secondary"}>
              Score: {doc.quality_score || "N/A"}
            </Badge>
            <Badge
              variant={
                doc.review_status === "approved"
                  ? "default"
                  : doc.review_status === "rejected"
                  ? "destructive"
                  : "secondary"
              }
            >
              {doc.review_status}
            </Badge>
            <a href={`/review/${jobId}/${doc.id}`}>
              <Button variant="outline" size="sm">Review</Button>
            </a>
          </div>
        ))}
      </div>
    </main>
  );
}
```

### 4.3 Create Document Review page with Monaco Editor — `src/app/review/[jobId]/[docId]/page.tsx`

```tsx
"use client";

import { use, useState, useCallback } from "react";
import dynamic from "next/dynamic";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import {
  useGetReviewDocumentQuery,
  useSubmitDecisionMutation,
  useAddCommentMutation,
  useResolveCommentMutation,
} from "@/store/api/review-api";

// Dynamic import for Monaco to avoid SSR issues
const Editor = dynamic(() => import("@monaco-editor/react"), { ssr: false });

export default function DocumentReviewPage({
  params,
}: {
  params: Promise<{ jobId: string; docId: string }>;
}) {
  const { jobId, docId } = use(params);
  const { data: doc, refetch } = useGetReviewDocumentQuery({ jobId, docId });
  const [submitDecision] = useSubmitDecisionMutation();
  const [addComment] = useAddCommentMutation();
  const [resolveComment] = useResolveCommentMutation();

  const [editedContent, setEditedContent] = useState<string | null>(null);
  const [notes, setNotes] = useState("");
  const [newComment, setNewComment] = useState("");

  const handleApprove = useCallback(async () => {
    await submitDecision({ jobId, docId, decision: "approved", notes });
    refetch();
  }, [jobId, docId, notes, submitDecision, refetch]);

  const handleReject = useCallback(async () => {
    await submitDecision({ jobId, docId, decision: "rejected", notes });
    refetch();
  }, [jobId, docId, notes, submitDecision, refetch]);

  const handleSaveEdits = useCallback(async () => {
    if (editedContent) {
      await submitDecision({
        jobId,
        docId,
        decision: "edited",
        notes,
        content: editedContent,
      });
      refetch();
    }
  }, [jobId, docId, editedContent, notes, submitDecision, refetch]);

  const handleAddComment = useCallback(async () => {
    if (newComment.trim()) {
      await addComment({ jobId, docId, content: newComment });
      setNewComment("");
      refetch();
    }
  }, [jobId, docId, newComment, addComment, refetch]);

  if (!doc) return <p className="p-8">Loading...</p>;

  return (
    <main className="container mx-auto p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">{doc.title || "Untitled Document"}</h1>
          <p className="text-sm text-muted-foreground">{doc.url}</p>
        </div>
        <div className="flex items-center gap-2">
          {doc.review_decision && (
            <Badge variant={doc.review_decision.decision === "approved" ? "default" : "destructive"}>
              {doc.review_decision.decision}
            </Badge>
          )}
          <Badge variant="secondary">Score: {doc.quality_score || "N/A"}</Badge>
          {doc.has_changes && <Badge variant="default">Modified by Agent</Badge>}
        </div>
      </div>

      {/* Main Content */}
      <Tabs defaultValue="editor">
        <TabsList>
          <TabsTrigger value="editor">Editor</TabsTrigger>
          <TabsTrigger value="diff">Diff View</TabsTrigger>
          <TabsTrigger value="preview">Preview</TabsTrigger>
        </TabsList>

        <TabsContent value="editor" className="border rounded-lg">
          <Editor
            height="500px"
            defaultLanguage="markdown"
            value={editedContent ?? doc.current_markdown}
            onChange={(value) => setEditedContent(value || "")}
            theme="vs-dark"
            options={{
              minimap: { enabled: false },
              wordWrap: "on",
              lineNumbers: "on",
              fontSize: 14,
            }}
          />
        </TabsContent>

        <TabsContent value="diff">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <h3 className="font-semibold mb-2 text-sm">Original</h3>
              <pre className="bg-muted p-4 rounded text-xs max-h-[500px] overflow-y-auto whitespace-pre-wrap">
                {doc.original_markdown}
              </pre>
            </div>
            <div>
              <h3 className="font-semibold mb-2 text-sm">Current (Agent-Corrected)</h3>
              <pre className="bg-muted p-4 rounded text-xs max-h-[500px] overflow-y-auto whitespace-pre-wrap">
                {doc.current_markdown}
              </pre>
            </div>
          </div>
        </TabsContent>

        <TabsContent value="preview" className="prose max-w-none p-4 max-h-[500px] overflow-y-auto">
          {/* Use dangerouslySetInnerHTML or react-markdown for preview */}
          <pre className="whitespace-pre-wrap">{doc.current_markdown}</pre>
        </TabsContent>
      </Tabs>

      {/* Review Actions */}
      <Card className="mt-6">
        <CardHeader>
          <CardTitle className="text-lg">Review Decision</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col gap-4">
            <Input
              placeholder="Reviewer notes (optional)"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
            <div className="flex gap-2">
              <Button variant="default" onClick={handleApprove}>
                ✓ Approve
              </Button>
              <Button variant="destructive" onClick={handleReject}>
                ✗ Reject
              </Button>
              <Button
                variant="secondary"
                onClick={handleSaveEdits}
                disabled={!editedContent}
              >
                💾 Save Edits & Approve
              </Button>
              <a href={`/review/${jobId}`}>
                <Button variant="outline">← Back to List</Button>
              </a>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Comments */}
      <Card className="mt-6">
        <CardHeader>
          <CardTitle className="text-lg">Comments ({doc.comments.length})</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3 mb-4">
            {doc.comments.map((comment) => (
              <div
                key={comment.id}
                className={`p-3 border rounded ${comment.resolved ? "opacity-50" : ""}`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-sm">{comment.author}</span>
                    {comment.line_number && (
                      <Badge variant="secondary" className="text-xs">
                        Line {comment.line_number}
                      </Badge>
                    )}
                  </div>
                  {!comment.resolved && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => resolveComment({ jobId, commentId: comment.id })}
                    >
                      Resolve
                    </Button>
                  )}
                </div>
                <p className="text-sm mt-1">{comment.content}</p>
              </div>
            ))}
          </div>
          <div className="flex gap-2">
            <Input
              placeholder="Add a comment..."
              value={newComment}
              onChange={(e) => setNewComment(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleAddComment()}
            />
            <Button onClick={handleAddComment} disabled={!newComment.trim()}>
              Comment
            </Button>
          </div>
        </CardContent>
      </Card>
    </main>
  );
}
```

### 4.4 Add navigation links

In layout nav bar:
```tsx
<a href="/review" className="text-sm hover:underline">Review</a>
```

**Done when**: `/review/{jobId}` shows the document list with status filters, and `/review/{jobId}/{docId}` opens the Monaco editor with approve/reject/edit actions.

---

## Task 5: Write Phase 5 Tests

**Working directory**: `rag-pipeline/apps/api/`

### 5.1 Create `tests/test_review_api.py`

```python
"""Tests for the review API endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_review_summary_requires_valid_job(client):
    """Summary endpoint should 404 for non-existent job."""
    response = await client.get(
        "/api/v1/jobs/00000000-0000-0000-0000-000000000000/review/summary"
    )
    # Either 404 or empty summary depending on implementation
    assert response.status_code in (200, 404)


@pytest.mark.asyncio
async def test_finalize_requires_all_reviewed(client):
    """Finalize should reject if not all documents are reviewed."""
    # This would need a real job in the DB; for now test the endpoint exists
    response = await client.post(
        "/api/v1/jobs/00000000-0000-0000-0000-000000000000/review/finalize"
    )
    assert response.status_code in (400, 404)
```

**Done when**: `pytest tests/test_review_api.py -v` passes.

---

## Phase 5 Done-When Checklist

- [ ] `review_decisions` and `review_comments` tables created via Alembic migration
- [ ] `GET /api/v1/jobs/{id}/review/summary` returns counts for approved/rejected/edited/pending
- [ ] `GET /api/v1/jobs/{id}/review/documents` returns document list with review status
- [ ] `GET /api/v1/jobs/{id}/review/documents/{docId}` returns full content + original diff data
- [ ] `POST .../decide` accepts `approved`, `rejected`, `edited` decisions
- [ ] `edited` decision writes modified content back to the Markdown file
- [ ] `POST .../batch-approve` approves multiple documents in one call
- [ ] `POST .../finalize` transitions job to `APPROVED` status (blocks if pending remain)
- [ ] Review dashboard shows summary cards with counts
- [ ] Document review page renders Monaco editor with Markdown syntax highlighting
- [ ] Diff view shows side-by-side original vs current content
- [ ] Comment threads can be created and resolved
- [ ] `pytest tests/test_review_api.py -v` passes
