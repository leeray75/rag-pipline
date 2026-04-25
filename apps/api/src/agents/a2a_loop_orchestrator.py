"""A2A Protocol v1.0 client orchestrator for the iterative Audit <-> Correct loop."""

import uuid

from a2a.client import Client, ClientConfig, ClientFactory
from a2a.types import Task, TaskState

from src.agents.a2a_helpers import make_user_message, extract_artifact_data

import structlog

logger = structlog.get_logger()

DEFAULT_MAX_ROUNDS = 10


def create_a2a_client(url: str) -> Client:
    """Create an A2A client with proper configuration."""
    config = ClientConfig(
        streaming=True,
        polling=False,
        supported_protocol_bindings=["JSONRPC", "HTTP+JSON"],
        accepted_output_modes=["text", "data", "file"],
    )
    factory = ClientFactory(config=config)
    return factory.create_from_url(url)


async def run_audit_correct_loop(
    audit_client: Client,
    correction_client: Client,
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
        audit_client: Client configured for the audit agent server.
        correction_client: Client configured for the correction agent server.
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
