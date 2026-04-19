"""Tests for A2A helper functions and agent card builders."""

from a2a.types import Task, TaskState, Role

from src.agents.a2a_helpers import (
    make_user_message,
    make_agent_message,
    make_task_status,
    make_artifact,
    extract_artifact_data,
)
from src.agents.a2a_agent_cards import (
    build_audit_agent_card,
    build_correction_agent_card,
)


def test_make_user_message_has_data_part():
    """User message should contain a DataPart with the provided data."""
    msg = make_user_message(
        context_id="ctx-1", data={"job_id": "j1"}, text="Hello",
    )
    assert msg.role == Role.user
    assert msg.context_id == "ctx-1"
    assert len(msg.parts) == 2  # TextPart + DataPart
    # DataPart is wrapped in a Part with a 'root' attribute
    assert hasattr(msg.parts[1].root, "data")
    assert msg.parts[1].root.data["job_id"] == "j1"


def test_make_user_message_without_text():
    """User message without text should have only a DataPart."""
    msg = make_user_message(context_id="ctx-2", data={"round": 1})
    assert len(msg.parts) == 1  # DataPart only (wrapped in Part)
    assert hasattr(msg.parts[0].root, "data")


def test_make_agent_message_has_text():
    """Agent message should contain a TextPart."""
    msg = make_agent_message(
        context_id="ctx-1", task_id="t-1", text="Done",
    )
    assert msg.role == Role.agent
    assert msg.task_id == "t-1"
    assert hasattr(msg.parts[0].root, "text")
    assert msg.parts[0].root.text == "Done"


def test_make_task_status_working():
    """TaskStatus should have the correct state and timestamp."""
    status = make_task_status(TaskState.working)
    assert status.state == TaskState.working
    assert status.timestamp is not None


def test_make_artifact_contains_data():
    """Artifact should contain a DataPart with the provided data."""
    artifact = make_artifact(
        name="test", description="desc", data={"key": "val"},
    )
    assert artifact.name == "test"
    assert hasattr(artifact.parts[0].root, "data")
    assert artifact.parts[0].root.data["key"] == "val"


def test_extract_artifact_data_from_task():
    """extract_artifact_data should pull data from the first artifact."""
    artifact = make_artifact(
        name="r", description="d", data={"total_issues": 5},
    )
    task = Task(
        id="t-1",
        context_id="ctx-1",
        status=make_task_status(TaskState.completed),
        artifacts=[artifact],
    )
    data = extract_artifact_data(task)
    assert data["total_issues"] == 5


def test_extract_artifact_data_empty_task():
    """extract_artifact_data should return empty dict for no artifacts."""
    task = Task(
        id="t-1",
        context_id="ctx-1",
        status=make_task_status(TaskState.completed),
        artifacts=[],
    )
    assert extract_artifact_data(task) == {}


def test_audit_agent_card_structure():
    """Audit AgentCard should have correct name, skills, and capabilities."""
    card = build_audit_agent_card("http://localhost:8000")
    assert card.name == "RAG Pipeline Audit Agent"
    assert len(card.skills) == 1
    assert card.skills[0].id == "audit-documents"
    assert card.capabilities.streaming is True
    assert card.url == "http://localhost:8000/a2a/audit"


def test_correction_agent_card_structure():
    """Correction AgentCard should have correct name and skills."""
    card = build_correction_agent_card("http://localhost:8000")
    assert card.name == "RAG Pipeline Correction Agent"
    assert len(card.skills) == 1
    assert card.skills[0].id == "correct-documents"
    assert card.url == "http://localhost:8000/a2a/correction"
