# Phase 3, Subtask 2 — Audit API Endpoints + Celery Integration

> **Phase**: Phase 3 — Audit Agent
> **Prerequisites**: Phase 2 complete — crawl pipeline produces Markdown files with frontmatter in staging directories, API endpoints for jobs/documents work, Celery task chain runs.
> **Prior Phase 3 Subtasks Required**: Subtask 1 complete — `schema_validator.py`, `audit_state.py`, and `audit_agent.py` exist in `src/agents/`, LangGraph/LangChain dependencies installed, `run_audit()` function is available.
> **Estimated Scope**: 2 files to create/modify

---

## Context

This subtask builds the FastAPI router that exposes audit functionality via REST endpoints. It creates three endpoints: triggering an audit on a job's staged documents, listing all audit reports for a job, and retrieving a specific report with full per-document issue details. The audit is triggered by calling the `run_audit()` function from Subtask 1, and results are persisted to Postgres via the `AuditReport` SQLAlchemy model.

### Key Assumptions from Prior Work

- The `IngestionJob` SQLAlchemy model exists (from Phase 1) with fields including `id`, `status`, and `current_audit_round`
- The `AuditReport` SQLAlchemy model exists (from Phase 1) with fields: `id`, `job_id`, `round`, `total_issues`, `issues_json`, `summary`, `status`, `agent_notes`, `created_at`
- `JobStatus` enum includes `AUDITING` and `REVIEW` values
- The `get_db` async session dependency is available from `src/database`
- The `run_audit()` async function from Subtask 1 is importable from `src.agents.audit_agent`

---

## Relevant Technology Stack (Pinned Versions)

| Package | Version | Notes |
|---|---|---|
| Python | 3.13.x | Runtime |
| FastAPI | 0.135.3 | API framework |
| SQLAlchemy | 2.0.49 | Async ORM |
| Pydantic | 2.13.0 | Request/response validation |
| Celery | 5.6.3 | Async task execution (optional wrapper) |
| structlog | 25.4.0 | Structured logging |

---

## Step-by-Step Implementation Instructions

### Step 1: Create the Audit Router

**Working directory**: `rag-pipeline/apps/api/src/routers/`

#### 1.1 Create `audit.py`

```python
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
```

---

### Step 2: Register the Audit Router

**Working directory**: `rag-pipeline/apps/api/src/`

#### 2.1 Update `main.py`

Add the audit router import and registration alongside existing routers:

```python
from src.routers import health, jobs, websocket, audit

app.include_router(audit.router, prefix="/api/v1", tags=["audit"])
```

This should be added in the same section where other routers are registered (e.g., `health.router`, `jobs.router`, `websocket.router`).

---

### Step 3 (Optional): Celery Task Wrapper

If the audit should run asynchronously via Celery instead of blocking the HTTP request, create a Celery task wrapper. This is optional for Phase 3 — the synchronous `await run_audit()` approach works for initial implementation.

**Working directory**: `rag-pipeline/apps/api/src/workers/`

If you choose to add a Celery wrapper, add a task in the existing workers module:

```python
# In src/workers/tasks.py (or a new src/workers/audit_tasks.py)
import asyncio
from src.agents.audit_agent import run_audit

@celery_app.task(name="run_audit_task")
def run_audit_task(job_id: str, audit_round: int = 1):
    """Celery task wrapper for the audit agent."""
    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(run_audit(job_id, audit_round))
        return result
    finally:
        loop.close()
```

Then in the `trigger_audit` endpoint, replace the direct `await run_audit()` call with:

```python
from src.workers.tasks import run_audit_task
run_audit_task.delay(str(job_id), next_round)
```

**Note**: If using Celery, the endpoint should return 202 Accepted immediately and the report will be saved by the Celery task. The client would poll `GET /jobs/{id}/audit-reports` to check for completion.

---

## Files to Create/Modify

| Action | File Path |
|---|---|
| Create | `rag-pipeline/apps/api/src/routers/audit.py` |
| Modify | `rag-pipeline/apps/api/src/main.py` |

---

## Done-When Checklist

- [ ] `POST /api/v1/jobs/{id}/audit` triggers the audit agent and returns a report summary with status 202
- [ ] `GET /api/v1/jobs/{id}/audit-reports` returns list of reports ordered by round
- [ ] `GET /api/v1/jobs/{id}/audit-reports/{report_id}` returns full report with per-document issues
- [ ] Job status transitions to `AUDITING` when audit starts
- [ ] Job status transitions to `REVIEW` when audit passes with zero issues
- [ ] Audit report is persisted to Postgres `AuditReport` table
- [ ] Router is registered in `main.py` with prefix `/api/v1` and tag `audit`

---

## Summary Report

Upon completion of this subtask, create a summary report at:
`rag-pipeline/ai-workspace/summary-reports/phase-3-subtask-2-audit-api-endpoints-summary.md`

The summary report must include:
- **Subtask**: Phase 3, Subtask 2 — Audit API Endpoints + Celery Integration
- **Status**: Complete / Partial / Blocked
- **Date**: {ISO 8601 date}
- **Files Created/Modified**: List every file path
- **Key Decisions**: Any deviations from the plan and why
- **Issues Encountered**: Problems and resolutions
- **Dependencies for Next Subtask**: What the next subtask needs to know
- **Verification Results**: Output of Done-When checklist items
