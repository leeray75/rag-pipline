"""A2A Protocol v1.0 — Helper functions for Messages, Parts, and Artifacts."""

import uuid
from datetime import datetime, timezone

from a2a.types import (
    Artifact,
    DataPart,
    Message,
    Part,
    Role,
    Task,
    TaskState,
    TaskStatus,
    TextPart,
)


def make_user_message(context_id: str, data: dict, text: str = "") -> Message:
    """Build a user Message with a DataPart payload."""
    parts: list[Part] = []
    if text:
        parts.append(TextPart(text=text))
    parts.append(DataPart(data=data))
    return Message(
        messageId=str(uuid.uuid4()),
        role=Role.user,
        parts=parts,
        contextId=context_id,
    )


def make_agent_message(
    context_id: str, task_id: str, text: str, data: dict | None = None,
) -> Message:
    """Build an agent Message with text and optional data."""
    parts: list[Part] = [TextPart(text=text)]
    if data:
        parts.append(DataPart(data=data))
    return Message(
        messageId=str(uuid.uuid4()),
        role=Role.agent,
        parts=parts,
        contextId=context_id,
        taskId=task_id,
    )


def make_task_status(
    state: TaskState, message: Message | None = None,
) -> TaskStatus:
    """Build a TaskStatus with current timestamp."""
    return TaskStatus(
        state=state,
        message=message,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


def make_artifact(name: str, description: str, data: dict) -> Artifact:
    """Build an Artifact containing a DataPart."""
    return Artifact(
        artifactId=str(uuid.uuid4()),
        name=name,
        description=description,
        parts=[DataPart(data=data)],
    )


def extract_artifact_data(task: Task) -> dict:
    """Extract the first DataPart from the first artifact of a Task."""
    if task.artifacts:
        # DataPart is wrapped in a Part with a 'root' attribute
        for part in task.artifacts[0].parts:
            # Check if it's a DataPart (via Part.root or direct data attribute)
            if hasattr(part, 'root') and hasattr(part.root, 'data'):
                return part.root.data
            if hasattr(part, 'data'):
                return part.data
    return {}
