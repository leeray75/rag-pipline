# Phase 4, Subtask 1 — A2A Agent Cards, Correction Agent & A2A Server Wrappers

> **Phase**: Phase 4 — Correction Agent & Iterative Audit Loop (A2A Protocol v1.0)
> **Subtask**: 1 of 3
> **Prerequisites**: Phase 3 complete (Audit Agent produces structured JSON reports via `run_audit()`, audit API endpoints work, audit reports stored in Postgres). No prior Phase 4 subtasks required.
> **Scope**: 6 new files in `rag-pipeline/apps/api/src/agents/`

---

## Objective

Install the `a2a-sdk` package and create the A2A Protocol v1.0 foundation: Agent Card definitions for both agents, helper functions for building `Message`/`Part`/`Artifact`/`Task` objects, the LangGraph Correction Agent, and A2A server wrappers that expose both the Audit Agent (from Phase 3) and the new Correction Agent as proper A2A agent servers.

---

## Relevant Technology Stack

| Package | Version | Install |
|---|---|---|
| Python | 3.13.x | Runtime |
| a2a-sdk | latest | `pip install a2a-sdk` |
| FastAPI | 0.135.3 | `pip install "fastapi[standard]"` |
| Pydantic | 2.13.0 | `pip install pydantic` |
| LangGraph | 1.1.6 | `pip install langgraph` |
| LangChain | 1.2.15 | `pip install langchain` |
| structlog | 25.4.0 | `pip install structlog` |

---

## Files to Create/Modify

| Action | File Path |
|---|---|
| **Modify** | `rag-pipeline/apps/api/pyproject.toml` (add `a2a-sdk` dependency) |
| **Create** | `rag-pipeline/apps/api/src/agents/a2a_agent_cards.py` |
| **Create** | `rag-pipeline/apps/api/src/agents/a2a_helpers.py` |
| **Create** | `rag-pipeline/apps/api/src/agents/correction_state.py` |
| **Create** | `rag-pipeline/apps/api/src/agents/correction_agent.py` |
| **Create** | `rag-pipeline/apps/api/src/agents/a2a_audit_server.py` |
| **Create** | `rag-pipeline/apps/api/src/agents/a2a_correction_server.py` |

---

## Step 1: Add `a2a-sdk` Dependency

**Path**: `rag-pipeline/apps/api/pyproject.toml`

Add to the `[project.dependencies]` list:

```toml
"a2a-sdk",
```

Then install:

```bash
cd rag-pipeline/apps/api && pip install a2a-sdk
```

---

## Step 2: Create `a2a_agent_cards.py`

**Path**: `rag-pipeline/apps/api/src/agents/a2a_agent_cards.py`

Defines `AgentCard` objects for both agents using official `a2a.types`. Each card describes the agent's name, capabilities, and skills for A2A discovery.

```python
"""A2A Protocol v1.0 — Agent Card definitions for Audit and Correction agents."""

from a2a.types import AgentCard, AgentSkill, AgentCapabilities


def build_audit_agent_card(base_url: str) -> AgentCard:
    """Build the AgentCard for the Audit Agent."""
    return AgentCard(
        name="RAG Pipeline Audit Agent",
        description="Validates Markdown documents against a 10-rule schema. "
        "Produces structured audit reports with issue classifications.",
        url=f"{base_url}/a2a/audit",
        version="1.0.0",
        capabilities=AgentCapabilities(streaming=True, pushNotifications=False),
        skills=[
            AgentSkill(
                id="audit-documents",
                name="Audit Documents",
                description="Run schema validation and quality audit on staged Markdown documents.",
                tags=["audit", "validation", "markdown", "quality"],
                examples=["Audit all documents for job abc-123"],
                inputModes=["application/json"],
                outputModes=["application/json"],
            ),
        ],
    )


def build_correction_agent_card(base_url: str) -> AgentCard:
    """Build the AgentCard for the Correction Agent."""
    return AgentCard(
        name="RAG Pipeline Correction Agent",
        description="Classifies audit issues as LEGITIMATE or FALSE_POSITIVE using an LLM, "
        "then applies corrections to Markdown documents.",
        url=f"{base_url}/a2a/correction",
        version="1.0.0",
        capabilities=AgentCapabilities(streaming=True, pushNotifications=False),
        skills=[
            AgentSkill(
                id="correct-documents",
                name="Correct Documents",
                description="Classify audit issues and apply corrections to Markdown documents.",
                tags=["correction", "markdown", "llm", "classification"],
                examples=["Correct documents based on audit report rpt-456"],
                inputModes=["application/json"],
                outputModes=["application/json"],
            ),
        ],
    )
```

---

## Step 3: Create `a2a_helpers.py`

**Path**: `rag-pipeline/apps/api/src/agents/a2a_helpers.py`

Helper functions for constructing A2A protocol objects: `Message` with `Part` unions, `TaskStatus`, `Artifact`, and a utility to extract data from task artifacts.

```python
"""A2A Protocol v1.0 — Helper functions for Messages, Parts, and Artifacts."""

import uuid
from datetime import datetime, timezone

from a2a.types import (
    Artifact, DataPart, Message, Part, Role,
    Task, TaskState, TaskStatus, TextPart,
)


def make_user_message(context_id: str, data: dict, text: str = "") -> Message:
    """Build a ROLE_USER Message with a DataPart payload."""
    parts: list[Part] = []
    if text:
        parts.append(TextPart(text=text))
    parts.append(DataPart(data=data))
    return Message(
        messageId=str(uuid.uuid4()),
        role=Role.ROLE_USER,
        parts=parts,
        contextId=context_id,
    )


def make_agent_message(
    context_id: str, task_id: str, text: str, data: dict | None = None,
) -> Message:
    """Build a ROLE_AGENT Message with text and optional data."""
    parts: list[Part] = [TextPart(text=text)]
    if data:
        parts.append(DataPart(data=data))
    return Message(
        messageId=str(uuid.uuid4()),
        role=Role.ROLE_AGENT,
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
        for part in task.artifacts[0].parts:
            if hasattr(part, "data"):
                return part.data
    return {}
```

---

## Step 4: Create `correction_state.py`

**Path**: `rag-pipeline/apps/api/src/agents/correction_state.py`

```python
"""State definition for the Correction Agent LangGraph workflow."""

from typing import TypedDict


class CorrectionIssue(TypedDict):
    """An issue to be classified and potentially corrected."""
    issue_id: str
    issue_type: str
    severity: str
    field: str | None
    message: str
    line: int | None
    suggestion: str | None
    classification: str  # "LEGITIMATE" | "FALSE_POSITIVE" | "pending"
    reasoning: str
    correction: str


class CorrectionDocInfo(TypedDict):
    """A document being corrected."""
    doc_id: str
    doc_path: str
    url: str
    title: str
    original_content: str
    corrected_content: str
    issues: list[CorrectionIssue]
    changes_made: list[str]
    status: str  # "pending" | "corrected" | "unchanged"


class CorrectionState(TypedDict):
    """State for the Correction Agent graph."""
    job_id: str
    round: int
    report_id: str
    documents: list[CorrectionDocInfo]
    total_legitimate: int
    total_false_positive: int
    total_corrected: int
    status: str  # "running" | "complete"
```

---

## Step 5: Create `correction_agent.py`

**Path**: `rag-pipeline/apps/api/src/agents/correction_agent.py`

6-node LangGraph workflow: `receive_report` → `classify_issues` → `plan_corrections` → `apply_corrections` → `save_corrections` → `emit_complete`. Returns structured results consumed by the A2A server wrapper.

```python
"""LangGraph Correction Agent — classifies issues and applies corrections."""

import json
from pathlib import Path

from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, START, END

from src.agents.correction_state import (
    CorrectionState, CorrectionDocInfo, CorrectionIssue,
)

import structlog

logger = structlog.get_logger()
STAGING_DIR = Path("/app/data/staging")


def receive_report(state: CorrectionState) -> dict:
    """Load the audit report and prepare documents for correction."""
    job_dir = STAGING_DIR / state["job_id"]
    report_path = job_dir / f"audit_report_round_{state['round']}.json"
    if not report_path.exists():
        logger.error("audit_report_not_found", path=str(report_path))
        return {"status": "failed"}

    report = json.loads(report_path.read_text(encoding="utf-8"))
    documents: list[CorrectionDocInfo] = []
    for doc_data in report.get("documents", []):
        if not doc_data.get("issues"):
            continue
        doc_path = Path(doc_data["doc_path"])
        content = doc_path.read_text(encoding="utf-8") if doc_path.exists() else ""
        issues = [
            CorrectionIssue(
                issue_id=issue["id"], issue_type=issue["type"],
                severity=issue["severity"], field=issue.get("field"),
                message=issue["message"], line=issue.get("line"),
                suggestion=issue.get("suggestion"),
                classification="pending", reasoning="", correction="",
            )
            for issue in doc_data["issues"]
        ]
        documents.append(CorrectionDocInfo(
            doc_id=doc_data["doc_id"], doc_path=str(doc_path),
            url=doc_data.get("url", ""), title=doc_data.get("title", ""),
            original_content=content, corrected_content=content,
            issues=issues, changes_made=[], status="pending",
        ))
    logger.info("report_received", job_id=state["job_id"], docs=len(documents))
    return {"documents": documents}


async def classify_issues(state: CorrectionState) -> dict:
    """Use Claude to classify each issue as LEGITIMATE or FALSE_POSITIVE."""
    llm = ChatAnthropic(model="claude-sonnet-4-20250514", max_tokens=2048, temperature=0)
    for doc in state["documents"]:
        excerpt = doc["original_content"][:2000]
        for issue in doc["issues"]:
            prompt = (
                "Classify this audit issue. Respond with ONLY JSON: "
                '{"classification": "LEGITIMATE"|"FALSE_POSITIVE", "reasoning": "...", "correction": "..."}\n\n'
                f"Issue: [{issue['issue_type']}] {issue['message']}\n"
                f"Severity: {issue['severity']}\nSuggestion: {issue['suggestion'] or 'N/A'}\n\n"
                f"Document excerpt:\n{excerpt}"
            )
            try:
                resp = await llm.ainvoke(prompt)
                content = resp.content
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0]
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0]
                result = json.loads(content.strip())
                issue["classification"] = result.get("classification", "LEGITIMATE")
                issue["reasoning"] = result.get("reasoning", "")
                issue["correction"] = result.get("correction", "")
            except Exception as e:
                logger.error("classification_failed", issue_id=issue["issue_id"], error=str(e))
                issue["classification"] = "LEGITIMATE"
                issue["reasoning"] = f"Classification failed: {e}. Defaulting to LEGITIMATE."
                issue["correction"] = issue.get("suggestion", "")
    return {"documents": state["documents"]}


def plan_corrections(state: CorrectionState) -> dict:
    """Count legitimate vs false positive issues per document."""
    total_leg, total_fp = 0, 0
    for doc in state["documents"]:
        leg = [i for i in doc["issues"] if i["classification"] == "LEGITIMATE"]
        fp = [i for i in doc["issues"] if i["classification"] == "FALSE_POSITIVE"]
        total_leg += len(leg)
        total_fp += len(fp)
        if not leg:
            doc["status"] = "unchanged"
            doc["changes_made"].append("All issues FALSE_POSITIVE; no changes")
        else:
            for issue in leg:
                doc["changes_made"].append(f"Plan: Fix {issue['issue_type']} — {issue['message']}")
    return {"documents": state["documents"], "total_legitimate": total_leg, "total_false_positive": total_fp}


async def apply_corrections(state: CorrectionState) -> dict:
    """Apply LLM-generated corrections to Markdown files."""
    llm = ChatAnthropic(model="claude-sonnet-4-20250514", max_tokens=4096, temperature=0)
    total_corrected = 0
    for doc in state["documents"]:
        legit = [i for i in doc["issues"] if i["classification"] == "LEGITIMATE"]
        if not legit:
            continue
        issues_text = "\n".join(
            f"- [{i['issue_type']}] {i['message']} → {i['correction']}" for i in legit
        )
        prompt = (
            "Apply ALL corrections to this Markdown. Return ONLY corrected Markdown.\n\n"
            f"CORRECTIONS:\n{issues_text}\n\nORIGINAL:\n{doc['original_content']}"
        )
        try:
            resp = await llm.ainvoke(prompt)
            corrected = resp.content.strip()
            if len(corrected) > len(doc["original_content"]) * 0.3:
                doc["corrected_content"] = corrected
                doc["status"] = "corrected"
                total_corrected += 1
                doc["changes_made"].append(f"Applied {len(legit)} corrections")
            else:
                doc["status"] = "unchanged"
                doc["changes_made"].append("LLM output too short; keeping original")
        except Exception as e:
            doc["status"] = "unchanged"
            doc["changes_made"].append(f"Correction failed: {e}")
    return {"documents": state["documents"], "total_corrected": total_corrected}


def save_corrections(state: CorrectionState) -> dict:
    """Write corrected Markdown back to staging with backup."""
    for doc in state["documents"]:
        if doc["status"] != "corrected":
            continue
        doc_path = Path(doc["doc_path"])
        if not doc_path.exists():
            continue
        backup = doc_path.with_suffix(f".round{state['round']}.bak.md")
        backup.write_text(doc["original_content"], encoding="utf-8")
        doc_path.write_text(doc["corrected_content"], encoding="utf-8")
        logger.info("correction_saved", doc=str(doc_path), backup=str(backup))
    return {}


def emit_complete(state: CorrectionState) -> dict:
    """Mark correction as complete."""
    logger.info("correction_complete", job_id=state["job_id"], round=state["round"],
                corrected=state["total_corrected"])
    return {"status": "complete"}


def build_correction_graph() -> StateGraph:
    """Construct the LangGraph correction agent workflow."""
    graph = StateGraph(CorrectionState)
    graph.add_node("receive_report", receive_report)
    graph.add_node("classify_issues", classify_issues)
    graph.add_node("plan_corrections", plan_corrections)
    graph.add_node("apply_corrections", apply_corrections)
    graph.add_node("save_corrections", save_corrections)
    graph.add_node("emit_complete", emit_complete)
    graph.add_edge(START, "receive_report")
    graph.add_edge("receive_report", "classify_issues")
    graph.add_edge("classify_issues", "plan_corrections")
    graph.add_edge("plan_corrections", "apply_corrections")
    graph.add_edge("apply_corrections", "save_corrections")
    graph.add_edge("save_corrections", "emit_complete")
    graph.add_edge("emit_complete", END)
    return graph.compile()


async def run_correction(job_id: str, correction_round: int, report_id: str) -> dict:
    """Run the correction agent. Returns the final correction state."""
    graph = build_correction_graph()
    initial: CorrectionState = {
        "job_id": job_id, "round": correction_round, "report_id": report_id,
        "documents": [], "total_legitimate": 0, "total_false_positive": 0,
        "total_corrected": 0, "status": "running",
    }
    return await graph.ainvoke(initial)
```

---

## Step 6: Create `a2a_audit_server.py`

**Path**: `rag-pipeline/apps/api/src/agents/a2a_audit_server.py`

A2A server wrapper for the Phase 3 Audit Agent. Accepts `SendMessageRequest`, extracts `job_id` and `round` from the `DataPart`, invokes `run_audit()`, and returns a `Task` with proper `TaskState` lifecycle and an `Artifact` containing the audit results.

```python
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
```

---

## Step 7: Create `a2a_correction_server.py`

**Path**: `rag-pipeline/apps/api/src/agents/a2a_correction_server.py`

A2A server wrapper for the Correction Agent. Same pattern as the audit server — extracts payload from `DataPart`, invokes `run_correction()`, returns `Task` with `Artifact`.

```python
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
```

---

## Done-When Checklist

- [ ] `a2a-sdk` is installed and `from a2a.types import Task, Message, AgentCard` works
- [ ] `build_audit_agent_card()` returns a valid `AgentCard` with `audit-documents` skill
- [ ] `build_correction_agent_card()` returns a valid `AgentCard` with `correct-documents` skill
- [ ] `make_user_message()`, `make_agent_message()`, `make_task_status()`, `make_artifact()` produce valid A2A types
- [ ] `extract_artifact_data()` extracts data from a `Task` artifact
- [ ] Correction Agent graph compiles: receive → classify → plan → apply → save → emit
- [ ] `await run_correction(job_id, round, report_id)` processes issues from audit report
- [ ] `AuditTaskHandler.on_message()` returns `Task` with `TASK_STATE_COMPLETED` and audit `Artifact`
- [ ] `CorrectionTaskHandler.on_message()` returns `Task` with `TASK_STATE_COMPLETED` and correction `Artifact`

---

## Summary Report

Upon completion of this subtask, create a summary report at:
`rag-pipeline/ai-workspace/summary-reports/phase-4-subtask-1-a2a-protocol-and-correction-agent-summary.md`

The summary report must include:
- **Subtask**: Phase 4, Subtask 1 — A2A Agent Cards, Correction Agent & A2A Server Wrappers
- **Status**: Complete / Partial / Blocked
- **Date**: ISO 8601 date
- **Files Created/Modified**: List every file path
- **Key Decisions**: Any deviations from the plan and why
- **Issues Encountered**: Problems and resolutions
- **Dependencies for Next Subtask**: What the next subtask needs to know
- **Verification Results**: Output of Done-When checklist items
