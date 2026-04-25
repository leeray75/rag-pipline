"""A2A Protocol v1.0 — Helper functions for Messages, Parts, and Artifacts."""

import uuid
from datetime import datetime, timezone

from a2a.types import Artifact, Message, Part, Role, Task, TaskState, TaskStatus
from google.protobuf import json_format
from google.protobuf.struct_pb2 import Value
from google.protobuf.timestamp_pb2 import Timestamp


def make_user_message(context_id: str, data: dict, text: str = "") -> Message:
    """Build a user Message with a data Part payload."""
    parts: list[Part] = []
    if text:
        parts.append(Part(text=text))
    data_value = json_format.ParseDict(data, Value())
    parts.append(Part(data=data_value))
    return Message(
        message_id=str(uuid.uuid4()),
        role=Role.ROLE_USER,
        parts=parts,
        context_id=context_id,
    )


def make_agent_message(
    context_id: str, task_id: str, text: str, data: dict | None = None,
) -> Message:
    """Build an agent Message with text and optional data."""
    parts: list[Part] = [Part(text=text)]
    if data:
        data_value = json_format.ParseDict(data, Value())
        parts.append(Part(data=data_value))
    return Message(
        message_id=str(uuid.uuid4()),
        role=Role.ROLE_AGENT,
        parts=parts,
        context_id=context_id,
        task_id=task_id,
    )


def make_task_status(
    state: TaskState, message: Message | None = None,
) -> TaskStatus:
    """Build a TaskStatus with current timestamp."""
    ts = Timestamp()
    ts.FromDatetime(datetime.now(timezone.utc))
    return TaskStatus(
        state=state,
        message=message,
        timestamp=ts,
    )


def make_artifact(name: str, description: str, data: dict) -> Artifact:
    """Build an Artifact containing a data Part."""
    data_value = json_format.ParseDict(data, Value())
    return Artifact(
        artifact_id=str(uuid.uuid4()),
        name=name,
        description=description,
        parts=[Part(data=data_value)],
    )


def extract_artifact_data(task: Task) -> dict:
    """Extract the data from the first Part of the first artifact of a Task."""
    if task.artifacts:
        for part in task.artifacts[0].parts:
            if hasattr(part, 'data') and part.data:
                return json_format.MessageToDict(part.data)
    return {}
