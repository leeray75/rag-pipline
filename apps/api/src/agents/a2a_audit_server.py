"""A2A Protocol v1.0 server wrapper for the Audit Agent (Phase 3)."""

import uuid
from a2a.server import A2AServer, TaskHandler
from a2a.types import SendMessageRequest, Task, TaskState

from src.agents.audit_agent import run_audit
from src.agents.a2a_helpers import make_agent_message, make_task_status, make_artifact

import structlog

logger = structlog.get_logger()


class AuditTaskHandler(TaskHandler):
    """Handle incoming A2A messages for the Audit Agent."""

    async def on_message(self, request: SendMessageRequest) -> Task:
        """Process an audit request via A2A protocol."""
        message = request.message
        task_id = str(uuid.uuid4())
        context_id = message.contextId or str(uuid.uuid4())

        payload = {}
        for part in message.parts:
            if hasattr(part, "data"):
                payload = part.data
                break

        job_id = payload.get("job_id", "")
        audit_round = payload.get("round", 1)

        task = Task(
            id=task_id, contextId=context_id,
            status=make_task_status(TaskState.TASK_STATE_WORKING),
            history=[message], artifacts=[],
        )

        try:
            result = await run_audit(job_id, audit_round=audit_round)
            artifact = make_artifact(
                name=f"audit-report-round-{audit_round}",
                description=f"Audit results for job {job_id} round {audit_round}",
                data={
                    "report_id": result.get("report_id", ""),
                    "total_issues": result.get("total_issues", 0),
                    "status": result.get("status", ""),
                },
            )
            msg = make_agent_message(
                context_id=context_id, task_id=task_id,
                text=f"Audit complete: {result.get('total_issues', 0)} issues found.",
                data={"report_id": result.get("report_id", ""),
                      "total_issues": result.get("total_issues", 0)},
            )
            task.status = make_task_status(TaskState.TASK_STATE_COMPLETED, msg)
            task.artifacts = [artifact]
        except Exception as e:
            logger.error("audit_task_failed", error=str(e))
            err = make_agent_message(
                context_id=context_id, task_id=task_id, text=f"Audit failed: {e}",
            )
            task.status = make_task_status(TaskState.TASK_STATE_FAILED, err)

        return task
