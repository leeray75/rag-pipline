"""API routes for audit reports and triggering audits."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.models import AuditReport, IngestionJob, JobStatus
from src.agents.audit_agent import run_audit

import structlog

logger = structlog.get_logger()

router = APIRouter()


@router.post("/jobs/{job_id}/audit", status_code=202)
async def trigger_audit(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Trigger an audit on a job's staged documents."""
    result = await db.execute(select(IngestionJob).where(IngestionJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Determine round number
    next_round = job.current_audit_round + 1

    # Update job status
    job.status = JobStatus.AUDITING
    job.current_audit_round = next_round
    await db.commit()

    # Run audit agent
    audit_result = await run_audit(str(job_id), audit_round=next_round)

    # Save report to Postgres
    report = AuditReport(
        job_id=job_id,
        round=next_round,
        total_issues=audit_result["total_issues"],
        issues_json={
            "documents": [
                {
                    "doc_id": doc["doc_id"],
                    "issues": doc["issues"],
                    "quality_score": doc["quality_score"],
                    "status": doc["status"],
                }
                for doc in audit_result["documents"]
            ]
        },
        summary=audit_result["summary"],
        status=audit_result["status"],
    )
    db.add(report)

    # Update job status based on result
    if audit_result["status"] == "approved":
        job.status = JobStatus.REVIEW  # Goes to human review
    else:
        job.status = JobStatus.AUDITING

    await db.commit()
    await db.refresh(report)

    return {
        "report_id": str(report.id),
        "round": next_round,
        "total_issues": audit_result["total_issues"],
        "summary": audit_result["summary"],
        "status": audit_result["status"],
    }


@router.get("/jobs/{job_id}/audit-reports")
async def list_audit_reports(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """List all audit reports for a job."""
    result = await db.execute(
        select(AuditReport)
        .where(AuditReport.job_id == job_id)
        .order_by(AuditReport.round)
    )
    reports = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "round": r.round,
            "total_issues": r.total_issues,
            "summary": r.summary,
            "status": r.status,
            "created_at": r.created_at.isoformat(),
        }
        for r in reports
    ]


@router.get("/jobs/{job_id}/audit-reports/{report_id}")
async def get_audit_report(
    job_id: uuid.UUID, report_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    """Get a full audit report with per-document issues."""
    result = await db.execute(
        select(AuditReport).where(
            AuditReport.id == report_id, AuditReport.job_id == job_id
        )
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    return {
        "id": str(report.id),
        "job_id": str(report.job_id),
        "round": report.round,
        "total_issues": report.total_issues,
        "issues_json": report.issues_json,
        "summary": report.summary,
        "status": report.status,
        "agent_notes": report.agent_notes,
        "created_at": report.created_at.isoformat(),
    }
