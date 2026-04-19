"""API routes for ingestion job management."""

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
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
