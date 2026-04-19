# Phase 2, Subtask 3 — API Router + WebSocket Progress

> **Phase**: Phase 2 — Crawl & Convert
> **Prerequisites**: Phase 1 complete + Phase 2 Subtasks 1–2 complete (fetcher, link discovery, converter, and Celery task chain all created)
> **Scope**: 2 files to create, 1 file to modify

---

## Relevant Technology Stack

| Package | Pinned Version | Purpose |
|---|---|---|
| Python | 3.13.x | Runtime |
| FastAPI | 0.135.3 | API framework with WebSocket support |
| SQLAlchemy | 2.0.49 | Async ORM for job/document queries |
| Pydantic | 2.13.0 | Request/response schemas |
| structlog | 25.4.0 | Structured logging |

### Key Imports from Prior Subtasks

These modules were created in Subtasks 1–2 and are imported by the router:

- `src.workers.crawl_tasks` — exports `start_crawl_pipeline`
- `src.models` — exports `Document`, `IngestionJob`, `JobStatus` (from Phase 1)
- `src.schemas` — exports `DocumentResponse`, `JobCreate`, `JobResponse`, `JobStatusResponse` (from Phase 1)
- `src.database` — exports `get_db` (from Phase 1)

---

## Step 1: Create the Jobs API Router

**Working directory**: `rag-pipeline/apps/api/src/routers/`

### 1.1 Create `jobs.py`

```python
"""API routes for ingestion job management."""

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.models import Document, IngestionJob, JobStatus
from src.schemas import DocumentResponse, JobCreate, JobResponse, JobStatusResponse
from src.workers.crawl_tasks import start_crawl_pipeline

import structlog

logger = structlog.get_logger()

router = APIRouter()

STAGING_DIR = Path("/app/data/staging")


@router.post("/jobs", response_model=JobResponse, status_code=201)
async def create_job(payload: JobCreate, db: AsyncSession = Depends(get_db)):
    """Create a new ingestion job and start the crawl pipeline."""
    job = IngestionJob(
        url=str(payload.url),
        crawl_all_docs=payload.crawl_all_docs,
        status=JobStatus.PENDING,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Start Celery pipeline
    start_crawl_pipeline(
        job_id=str(job.id),
        url=str(payload.url),
        crawl_all=payload.crawl_all_docs,
    )

    # Update status to crawling
    job.status = JobStatus.CRAWLING
    await db.commit()
    await db.refresh(job)

    logger.info("job_created", job_id=str(job.id), url=str(payload.url))
    return job


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get job details by ID."""
    result = await db.execute(select(IngestionJob).where(IngestionJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/jobs/{job_id}/status", response_model=JobStatusResponse)
async def get_job_status(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get lightweight job status for polling."""
    result = await db.execute(select(IngestionJob).where(IngestionJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/jobs/{job_id}/documents", response_model=list[DocumentResponse])
async def list_documents(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """List all documents for a job."""
    result = await db.execute(
        select(Document).where(Document.job_id == job_id).order_by(Document.created_at)
    )
    return result.scalars().all()


@router.get("/jobs/{job_id}/documents/{doc_id}")
async def get_document(job_id: uuid.UUID, doc_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get a single document with its raw HTML and Markdown content."""
    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.job_id == job_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    response = {
        "id": str(doc.id),
        "job_id": str(doc.job_id),
        "url": doc.url,
        "title": doc.title,
        "status": doc.status,
        "word_count": doc.word_count,
        "raw_html": None,
        "markdown": None,
    }

    # Read file contents if available
    if doc.raw_html_path:
        html_path = Path(doc.raw_html_path)
        if html_path.exists():
            response["raw_html"] = html_path.read_text(encoding="utf-8")

    if doc.markdown_path:
        md_path = Path(doc.markdown_path)
        if md_path.exists():
            response["markdown"] = md_path.read_text(encoding="utf-8")

    return response


@router.delete("/jobs/{job_id}/documents/{doc_id}", status_code=204)
async def delete_document(job_id: uuid.UUID, doc_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Remove a document from staging before audit."""
    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.job_id == job_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Delete files
    for path_str in [doc.raw_html_path, doc.markdown_path]:
        if path_str:
            p = Path(path_str)
            if p.exists():
                p.unlink()

    await db.delete(doc)
    await db.commit()
```

---

## Step 2: Create the WebSocket Progress Endpoint

**Working directory**: `rag-pipeline/apps/api/src/routers/`

### 2.1 Create `websocket.py`

```python
"""WebSocket endpoint for real-time crawl progress streaming."""

import asyncio
import json
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

import structlog

logger = structlog.get_logger()

router = APIRouter()

# In-memory connection manager (for single-instance; use Redis PubSub for multi-instance)
class ConnectionManager:
    """Manage WebSocket connections per job."""

    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, job_id: str, websocket: WebSocket):
        await websocket.accept()
        if job_id not in self.active_connections:
            self.active_connections[job_id] = []
        self.active_connections[job_id].append(websocket)

    def disconnect(self, job_id: str, websocket: WebSocket):
        if job_id in self.active_connections:
            self.active_connections[job_id].remove(websocket)
            if not self.active_connections[job_id]:
                del self.active_connections[job_id]

    async def broadcast(self, job_id: str, message: dict):
        """Send a message to all connections for a job."""
        if job_id in self.active_connections:
            data = json.dumps(message)
            for connection in self.active_connections[job_id]:
                try:
                    await connection.send_text(data)
                except Exception:
                    pass


manager = ConnectionManager()


@router.websocket("/jobs/{job_id}/stream")
async def job_progress_stream(websocket: WebSocket, job_id: str):
    """WebSocket endpoint for streaming crawl progress events."""
    await manager.connect(job_id, websocket)
    try:
        while True:
            # Keep connection alive; client can send heartbeats
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        manager.disconnect(job_id, websocket)
```

---

## Step 3: Register Routers in `src/main.py`

**Working directory**: `rag-pipeline/apps/api/`

Add these imports and router registrations to the existing `src/main.py`:

```python
from src.routers import health, jobs, websocket

# After existing router registration, add:
app.include_router(jobs.router, prefix="/api/v1", tags=["jobs"])
app.include_router(websocket.router, prefix="/api/v1/ws", tags=["websocket"])
```

**Note**: The `health` router import should already exist from Phase 1. Only add the `jobs` and `websocket` imports and their `include_router` calls.

---

## Files to Create/Modify

| Action | File Path |
|---|---|
| **Create** | `rag-pipeline/apps/api/src/routers/jobs.py` |
| **Create** | `rag-pipeline/apps/api/src/routers/websocket.py` |
| **Modify** | `rag-pipeline/apps/api/src/main.py` (add router registrations) |

---

## Done-When Checklist

- [ ] `POST /api/v1/jobs` with `{"url": "https://example.com", "crawl_all_docs": false}` returns 201 with a job object
- [ ] `GET /api/v1/jobs/{id}` returns job details
- [ ] `GET /api/v1/jobs/{id}/documents` returns the list of converted documents
- [ ] `GET /api/v1/jobs/{id}/documents/{doc_id}` returns Markdown + HTML content
- [ ] `DELETE /api/v1/jobs/{id}/documents/{doc_id}` returns 204 and removes the document
- [ ] WebSocket endpoint at `/api/v1/ws/jobs/{id}/stream` accepts connections
- [ ] WebSocket responds to `ping` with `{"type": "pong"}`

---

## Summary Report

Upon completion of this subtask, create a summary report at:
`rag-pipeline/ai-workspace/summary-reports/phase-2-subtask-3-api-and-websocket-summary.md`

The summary report must include:
- **Subtask**: Phase 2, Subtask 3 — API Router + WebSocket Progress
- **Status**: Complete / Partial / Blocked
- **Date**: {ISO 8601 date}
- **Files Created/Modified**: List every file path
- **Key Decisions**: Any deviations from the plan and why
- **Issues Encountered**: Problems and resolutions
- **Dependencies for Next Subtask**: What the next subtask needs to know
- **Verification Results**: Output of Done-When checklist items
