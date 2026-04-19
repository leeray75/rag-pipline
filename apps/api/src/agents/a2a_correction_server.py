"""A2A Protocol v1.0 server wrapper for the Correction Agent."""

import uuid
from a2a.server import A2AServer, TaskHandler
from a2a.types import SendMessageRequest, Task, TaskState

from src.agents.correction_agent import run_correction
from src.agents.a2a_helpers import make_agent_message, make_task_status, make_artifact

import structlog

logger = structlog.get_logger()


class CorrectionTaskHandler(TaskHandler):
    """Handle incoming A2A messages for the Correction Agent."""

    async def on_message(self, request: SendMessageRequest) -> Task:
        """Process a correction request via A2A protocol."""
        message = request.message
        task_id = str(uuid.uuid4())
        context_id = message.contextId or str(uuid.uuid4())

        payload = {}
        for part in message.parts:
            if hasattr(part, "data"):
                payload = part.data
                break

        job_id = payload.get("job_id", "")
        correction_round = payload.get("round", 1)
        report_id = payload.get("report_id", "")

        task = Task(
            id=task_id, contextId=context_id,
            status=make_task_status(TaskState.TASK_STATE_WORKING),
            history=[message], artifacts=[],
        )

        try:
            result = await run_correction(job_id, correction_round, report_id)
            artifact = make_artifact(
                name=f"correction-report-round-{correction_round}",
                description=f"Correction results for job {job_id} round {correction_round}",
                data={
                    "total_corrected": result.get("total_corrected", 0),
                    "total_legitimate": result.get("total_legitimate", 0),
                    "total_false_positive": result.get("total_false_positive", 0),
                    "status": result.get("status", "complete"),
                },
            )
            msg = make_agent_message(
                context_id=context_id, task_id=task_id,
                text=f"Correction complete: {result.get('total_corrected', 0)} docs corrected.",
            )
            task.status = make_task_status(TaskState.TASK_STATE_COMPLETED, msg)
            task.artifacts = [artifact]
        except Exception as e:
            logger.error("correction_task_failed", error=str(e))
            err = make_agent_message(
                context_id=context_id, task_id=task_id, text=f"Correction failed: {e}",
            )
            task.status = make_task_status(TaskState.TASK_STATE_FAILED, err)

        return task
