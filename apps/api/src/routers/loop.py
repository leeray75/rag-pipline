"""API routes for the audit-correct loop orchestration."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.database import get_db
from src.models import IngestionJob, JobStatus
from src.agents.a2a_loop_orchestrator import create_a2a_client, run_audit_correct_loop

import structlog

logger = structlog.get_logger()

router = APIRouter()


@router.post("/jobs/{job_id}/start-loop", status_code=202)
async def start_audit_loop(
    job_id: uuid.UUID,
    max_rounds: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Start the iterative audit-correct loop using A2A protocol.

    Creates A2AClient instances for both agent servers and runs the
    orchestrator loop until convergence or max_rounds.
    """
    result = await db.execute(
        select(IngestionJob).where(IngestionJob.id == job_id),
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    starting_round = job.current_audit_round + 1
    job.status = JobStatus.AUDITING
    await db.commit()

    # Create A2A clients for both agent servers using the helper function
    base_url = settings.a2a_base_url
    audit_client = create_a2a_client(url=f"{base_url}/a2a/audit")
    correction_client = create_a2a_client(url=f"{base_url}/a2a/correction")

    loop_result = await run_audit_correct_loop(
        audit_client=audit_client,
        correction_client=correction_client,
        job_id=str(job_id),
        max_rounds=max_rounds,
        starting_round=starting_round,
    )

    # Update job status based on loop result
    if loop_result["status"] in ("approved", "escalated"):
        job.status = JobStatus.REVIEW
    elif loop_result["status"] == "failed":
        job.status = JobStatus.FAILED
    job.current_audit_round = loop_result["final_round"]
    await db.commit()

    return loop_result


@router.post("/jobs/{job_id}/stop-loop", status_code=200)
async def stop_audit_loop(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Force-stop the audit loop and proceed to human review."""
    result = await db.execute(
        select(IngestionJob).where(IngestionJob.id == job_id),
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    job.status = JobStatus.REVIEW
    await db.commit()

    return {"status": "stopped", "message": "Loop stopped. Job sent to human review."}


@router.get("/jobs/{job_id}/loop-status")
async def get_loop_status(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get the current loop status for a job."""
    result = await db.execute(
        select(IngestionJob).where(IngestionJob.id == job_id),
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return {
        "job_id": str(job_id),
        "status": job.status,
        "current_round": job.current_audit_round,
    }
