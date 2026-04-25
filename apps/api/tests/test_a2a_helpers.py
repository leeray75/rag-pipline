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
    """User message should contain a Part with data."""
    msg = make_user_message(
        context_id="ctx-1", data={"job_id": "j1"}, text="Hello",
    )
    assert msg.role == Role.ROLE_USER
    assert msg.context_id == "ctx-1"
    assert len(msg.parts) == 2  # Text Part + Data Part
    assert msg.parts[1].data is not None


def test_make_user_message_without_text():
    """User message without text should have only a data Part."""
    msg = make_user_message(context_id="ctx-2", data={"round": 1})
    assert len(msg.parts) == 1  # Data Part only
    assert msg.parts[0].data is not None


def test_make_agent_message_has_text():
    """Agent message should contain a text Part."""
    msg = make_agent_message(
        context_id="ctx-1", task_id="t-1", text="Done",
    )
    assert msg.role == Role.ROLE_AGENT
    assert msg.task_id == "t-1"
    assert msg.parts[0].text == "Done"


def test_make_task_status_working():
    """TaskStatus should have the correct state and timestamp."""
    status = make_task_status(TaskState.TASK_STATE_WORKING)
    assert status.state == TaskState.TASK_STATE_WORKING
    assert status.timestamp is not None


def test_make_artifact_contains_data():
    """Artifact should contain a Part with data."""
    artifact = make_artifact(
        name="test", description="desc", data={"key": "val"},
    )
    assert artifact.name == "test"
    assert artifact.artifact_id is not None
    assert artifact.parts[0].data is not None


def test_extract_artifact_data_from_task():
    """extract_artifact_data should pull data from the first artifact."""
    artifact = make_artifact(
        name="r", description="d", data={"total_issues": 5},
    )
    task = Task(
        id="t-1",
        context_id="ctx-1",
        status=make_task_status(TaskState.TASK_STATE_COMPLETED),
        artifacts=[artifact],
    )
    data = extract_artifact_data(task)
    assert data["total_issues"] == 5


def test_extract_artifact_data_empty_task():
    """extract_artifact_data should return empty dict for no artifacts."""
    task = Task(
        id="t-1",
        context_id="ctx-1",
        status=make_task_status(TaskState.TASK_STATE_COMPLETED),
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
    assert len(card.supported_interfaces) == 1
    assert "a2a/audit" in card.supported_interfaces[0].url


def test_correction_agent_card_structure():
    """Correction AgentCard should have correct name and skills."""
    card = build_correction_agent_card("http://localhost:8000")
    assert card.name == "RAG Pipeline Correction Agent"
    assert len(card.skills) == 1
    assert card.skills[0].id == "correct-documents"
    assert len(card.supported_interfaces) == 1
    assert "a2a/correction" in card.supported_interfaces[0].url
