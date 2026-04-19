# Phase 4, Subtask 2 — A2A Client Orchestrator & Loop API Endpoints

> **Phase**: Phase 4 — Correction Agent & Iterative Audit Loop (A2A Protocol v1.0)
> **Subtask**: 2 of 3
> **Prerequisites**: Phase 3 complete + Phase 4 Subtask 1 complete (`a2a-sdk` installed, `a2a_agent_cards.py`, `a2a_helpers.py`, `correction_agent.py` with `run_correction()`, `a2a_audit_server.py` with `AuditTaskHandler`, `a2a_correction_server.py` with `CorrectionTaskHandler`).
> **Scope**: 1 new file in `agents/`, 2 new files in `routers/`, 1 modification to `main.py`

---

## Objective

Build the A2A client orchestrator that coordinates the iterative Audit ↔ Correct loop using the official `a2a.client.A2AClient` to send messages to both agent servers. Expose the loop via FastAPI endpoints and implement A2A agent discovery endpoints that serve `AgentCard` JSON at `/.well-known/agent-card.json` paths.

---

## Relevant Technology Stack

| Package | Version | Install |
|---|---|---|
| Python | 3.13.x | Runtime |
| a2a-sdk | latest | `pip install a2a-sdk` |
| FastAPI | 0.135.3 | `pip install "fastapi[standard]"` |
| Pydantic | 2.13.0 | `pip install pydantic` |
| SQLAlchemy | 2.0.49 | `pip install "sqlalchemy[asyncio]"` |
| structlog | 25.4.0 | `pip install structlog` |

---

## Files to Create/Modify

| Action | File Path |
|---|---|
| **Create** | `rag-pipeline/apps/api/src/agents/a2a_loop_orchestrator.py` |
| **Create** | `rag-pipeline/apps/api/src/routers/loop.py` |
| **Create** | `rag-pipeline/apps/api/src/routers/a2a_discovery.py` |
| **Modify** | `rag-pipeline/apps/api/src/main.py` (register loop + discovery routers) |

---

## Context: Dependencies from Subtask 1

This subtask depends on the following from Subtask 1:

- **`src.agents.a2a_helpers`** — imports `make_user_message`, `extract_artifact_data`
- **`src.agents.a2a_agent_cards`** — imports `build_audit_agent_card`, `build_correction_agent_card`
- **`src.agents.a2a_audit_server`** — `AuditTaskHandler` (A2A server for audit agent)
- **`src.agents.a2a_correction_server`** — `CorrectionTaskHandler` (A2A server for correction agent)

The A2A types used in this subtask:
- `Task` — returned by `A2AClient.send_message()`
- `TaskState` — `TASK_STATE_COMPLETED`, `TASK_STATE_FAILED`
- `Message` — built via `make_user_message()` with `DataPart` payload
- `AgentCard` — served at discovery endpoints

---

## Step 1: Create `a2a_loop_orchestrator.py`

**Path**: `rag-pipeline/apps/api/src/agents/a2a_loop_orchestrator.py`

This module orchestrates the iterative Audit ↔ Correct loop using `a2a.client.A2AClient` to send `Message` objects to each agent server. Each round: (1) send audit request → get `Task` with audit `Artifact`, (2) check if approved (zero issues), (3) send correction request → get `Task` with correction `Artifact`, (4) loop. Terminates on convergence or max rounds.

```python
"""A2A Protocol v1.0 client orchestrator for the iterative Audit <-> Correct loop."""

import uuid

from a2a.client import A2AClient
from a2a.types import Task, TaskState

from src.agents.a2a_helpers import make_user_message, extract_artifact_data

import structlog

logger = structlog.get_logger()

DEFAULT_MAX_ROUNDS = 10


async def run_audit_correct_loop(
    audit_client: A2AClient,
    correction_client: A2AClient,
    job_id: str,
    max_rounds: int = DEFAULT_MAX_ROUNDS,
    starting_round: int = 1,
) -> dict:
    """Run the Audit <-> Correct loop using A2A protocol clients.

    Each round:
    1. SendMessage to Audit Agent -> get Task with audit results
    2. Check if approved (zero issues) -> return approved
    3. SendMessage to Correction Agent -> get Task with correction results
    4. Loop until convergence or max_rounds

    Args:
        audit_client: A2AClient configured for the audit agent server.
        correction_client: A2AClient configured for the correction agent server.
        job_id: The ingestion job ID to process.
        max_rounds: Maximum number of audit-correct iterations.
        starting_round: The round number to start from.

    Returns:
        Dict with status, final_round, total_rounds, rounds log, and optional reason.
    """
    context_id = str(uuid.uuid4())  # Shared context for the entire loop
    rounds_log: list[dict] = []
    current_round = starting_round

    while current_round <= max_rounds:
        logger.info("loop_round_start", job_id=job_id, round=current_round)

        # --- Step 1: Send audit request via A2A ---
        audit_message = make_user_message(
            context_id=context_id,
            data={"job_id": job_id, "round": current_round},
            text=f"Audit documents for job {job_id}, round {current_round}",
        )
        audit_task: Task = await audit_client.send_message(audit_message)

        # Extract audit results from the Task's Artifact
        audit_data = extract_artifact_data(audit_task)
        round_entry = {
            "round": current_round,
            "audit_task_id": audit_task.id,
            "audit_task_state": audit_task.status.state,
            "audit_issues": audit_data.get("total_issues", 0),
            "audit_status": audit_data.get("status", ""),
            "report_id": audit_data.get("report_id", ""),
            "correction_applied": False,
            "docs_corrected": 0,
            "false_positives": 0,
        }

        # Check for audit failure
        if audit_task.status.state == TaskState.TASK_STATE_FAILED:
            rounds_log.append(round_entry)
            logger.error("audit_failed", job_id=job_id, round=current_round)
            return {
                "status": "failed",
                "final_round": current_round,
                "total_rounds": current_round - starting_round + 1,
                "rounds": rounds_log,
                "reason": "Audit agent failed",
            }

        # --- Step 2: Check if approved (zero issues) ---
        if audit_data.get("status") == "approved":
            rounds_log.append(round_entry)
            logger.info("loop_approved", job_id=job_id, final_round=current_round)
            return {
                "status": "approved",
                "final_round": current_round,
                "total_rounds": current_round - starting_round + 1,
                "rounds": rounds_log,
            }

        # --- Step 3: Send correction request via A2A ---
        correction_message = make_user_message(
            context_id=context_id,
            data={
                "job_id": job_id,
                "round": current_round,
                "report_id": audit_data.get("report_id", ""),
            },
            text=f"Correct documents for job {job_id}, round {current_round}",
        )
        correction_task: Task = await correction_client.send_message(
            correction_message,
        )

        # Extract correction results from the Task's Artifact
        correction_data = extract_artifact_data(correction_task)
        round_entry["correction_applied"] = True
        round_entry["correction_task_id"] = correction_task.id
        round_entry["correction_task_state"] = correction_task.status.state
        round_entry["docs_corrected"] = correction_data.get("total_corrected", 0)
        round_entry["false_positives"] = correction_data.get(
            "total_false_positive", 0,
        )
        rounds_log.append(round_entry)

        # Check for correction failure
        if correction_task.status.state == TaskState.TASK_STATE_FAILED:
            logger.error("correction_failed", job_id=job_id, round=current_round)
            return {
                "status": "failed",
                "final_round": current_round,
                "total_rounds": current_round - starting_round + 1,
                "rounds": rounds_log,
                "reason": "Correction agent failed",
            }

        current_round += 1

    # Max rounds exceeded — escalate to human review
    logger.warning(
        "loop_escalated",
        job_id=job_id,
        max_rounds=max_rounds,
        remaining_issues=rounds_log[-1]["audit_issues"] if rounds_log else 0,
    )
    return {
        "status": "escalated",
        "final_round": current_round - 1,
        "total_rounds": max_rounds,
        "rounds": rounds_log,
        "reason": f"Max rounds ({max_rounds}) exceeded without convergence",
    }
```

---

## Step 2: Create `loop.py` Router

**Path**: `rag-pipeline/apps/api/src/routers/loop.py`

Three API endpoints for loop control and monitoring. The `start-loop` endpoint creates `A2AClient` instances for both agent servers and delegates to the orchestrator.

```python
"""API routes for the audit-correct loop orchestration."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.models import IngestionJob, JobStatus
from src.agents.a2a_loop_orchestrator import run_audit_correct_loop

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

    # Create A2A clients for both agent servers
    from a2a.client import A2AClient

    base_url = "http://localhost:8000"
    audit_client = A2AClient(url=f"{base_url}/a2a/audit")
    correction_client = A2AClient(url=f"{base_url}/a2a/correction")

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
```

---

## Step 3: Create `a2a_discovery.py` — Agent Discovery Endpoints

**Path**: `rag-pipeline/apps/api/src/routers/a2a_discovery.py`

Serves `AgentCard` JSON at the standard A2A discovery paths with the `application/a2a+json` media type and `A2A-Version: 1.0` header.

```python
"""A2A Protocol v1.0 — Agent discovery endpoints."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from src.agents.a2a_agent_cards import (
    build_audit_agent_card,
    build_correction_agent_card,
)

router = APIRouter()

BASE_URL = "http://localhost:8000"


@router.get("/a2a/audit/.well-known/agent-card.json")
async def audit_agent_card():
    """Serve the Audit Agent AgentCard for A2A discovery."""
    card = build_audit_agent_card(BASE_URL)
    return JSONResponse(
        content=card.model_dump(),
        media_type="application/a2a+json",
        headers={"A2A-Version": "1.0"},
    )


@router.get("/a2a/correction/.well-known/agent-card.json")
async def correction_agent_card():
    """Serve the Correction Agent AgentCard for A2A discovery."""
    card = build_correction_agent_card(BASE_URL)
    return JSONResponse(
        content=card.model_dump(),
        media_type="application/a2a+json",
        headers={"A2A-Version": "1.0"},
    )
```

---

## Step 4: Register Routers in `main.py`

**Path**: `rag-pipeline/apps/api/src/main.py`

Add the loop and discovery router imports and registrations alongside existing routers.

**Add to imports:**

```python
from src.routers import health, jobs, websocket, audit, loop, a2a_discovery
```

**Add to router registration:**

```python
app.include_router(loop.router, prefix="/api/v1", tags=["loop"])
app.include_router(a2a_discovery.router, tags=["a2a-discovery"])
```

---

## API Endpoint Reference

| Method | Path | Description | Status Code |
|---|---|---|---|
| `POST` | `/api/v1/jobs/{id}/start-loop` | Start the A2A audit-correct loop | 202 |
| `POST` | `/api/v1/jobs/{id}/stop-loop` | Force-stop loop, send to human review | 200 |
| `GET` | `/api/v1/jobs/{id}/loop-status` | Get current loop state and round | 200 |
| `GET` | `/a2a/audit/.well-known/agent-card.json` | Audit Agent discovery card | 200 |
| `GET` | `/a2a/correction/.well-known/agent-card.json` | Correction Agent discovery card | 200 |

---

## Done-When Checklist

- [ ] `await run_audit_correct_loop(audit_client, correction_client, job_id)` iterates using A2A protocol
- [ ] Loop terminates on convergence (zero issues → approved) or max_rounds (→ escalated)
- [ ] Loop handles agent failures gracefully (→ failed status)
- [ ] `POST /api/v1/jobs/{id}/start-loop` triggers the A2A loop and returns round summaries
- [ ] `POST /api/v1/jobs/{id}/stop-loop` force-stops and sends to human review
- [ ] `GET /api/v1/jobs/{id}/loop-status` returns current loop state
- [ ] `GET /a2a/audit/.well-known/agent-card.json` returns valid `AgentCard` with `application/a2a+json`
- [ ] `GET /a2a/correction/.well-known/agent-card.json` returns valid `AgentCard` with `A2A-Version: 1.0` header
- [ ] Loop and discovery routers registered in `main.py`

---

## Summary Report

Upon completion of this subtask, create a summary report at:
`rag-pipeline/ai-workspace/summary-reports/phase-4-subtask-2-loop-orchestrator-and-api-summary.md`

The summary report must include:
- **Subtask**: Phase 4, Subtask 2 — A2A Client Orchestrator & Loop API Endpoints
- **Status**: Complete / Partial / Blocked
- **Date**: ISO 8601 date
- **Files Created/Modified**: List every file path
- **Key Decisions**: Any deviations from the plan and why
- **Issues Encountered**: Problems and resolutions
- **Dependencies for Next Subtask**: What the next subtask needs to know
- **Verification Results**: Output of Done-When checklist items
