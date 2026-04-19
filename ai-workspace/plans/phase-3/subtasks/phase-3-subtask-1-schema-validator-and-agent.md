# Phase 3, Subtask 1 — Dependencies + Schema Validator + LangGraph Audit Agent

> **Phase**: Phase 3 — Audit Agent
> **Prerequisites**: Phase 2 complete — crawl pipeline produces Markdown files with frontmatter in staging directories, API endpoints for jobs/documents work, Celery task chain runs.
> **Prior Phase 3 Subtasks Required**: None (this is the first subtask)
> **Estimated Scope**: 4 files to create/modify

---

## Context

This subtask implements the core audit agent infrastructure: adding LangGraph/LangChain dependencies, building a rule-based schema validator for Markdown documents, and constructing a 6-node LangGraph workflow that loads documents, validates schemas, assesses quality via LLM, checks for duplicates, compiles a report, and saves it to disk.

---

## Relevant Technology Stack (Pinned Versions)

| Package | Version | Install |
|---|---|---|
| Python | 3.13.x | Runtime |
| LangGraph | 1.1.6 | `pip install langgraph` |
| LangChain | 1.2.15 | `pip install langchain` |
| langchain-anthropic | 0.4.0+ | `pip install langchain-anthropic` |
| langchain-openai | 0.3.0+ | `pip install langchain-openai` |
| pydantic-ai | 0.1.0+ | `pip install pydantic-ai` |
| numpy | 2.0.0+ | `pip install numpy` |
| structlog | 25.4.0 | `pip install structlog` |
| Pydantic | 2.13.0 | `pip install pydantic` |

---

## Step-by-Step Implementation Instructions

### Step 1: Add Phase 3 Python Dependencies

**Working directory**: `rag-pipeline/apps/api/`

#### 1.1 Update `pyproject.toml` — add to `[project.dependencies]`

```toml
    "langgraph>=1.1.0",
    "langchain>=1.2.0",
    "langchain-anthropic>=0.4.0",
    "langchain-openai>=0.3.0",
    "pydantic-ai>=0.1.0",
    "numpy>=2.0.0",
```

#### 1.2 Install

```bash
pip install -e ".[dev]"
```

**Verify**: `python -c "import langgraph, langchain, langchain_anthropic"` succeeds.

---

### Step 2: Create the Document Schema Validator

**Working directory**: `rag-pipeline/apps/api/src/agents/`

#### 2.1 Create `schema_validator.py`

This is a rule-based validator — no LLM calls needed. It checks structural compliance.

```python
"""Rule-based Markdown document schema validator."""

import re
import yaml
from dataclasses import dataclass, field
from pathlib import Path

import structlog

logger = structlog.get_logger()


@dataclass
class SchemaIssue:
    """A single schema violation found in a document."""
    issue_id: str
    issue_type: str
    severity: str  # "critical" | "warning" | "info"
    field: str | None
    message: str
    line: int | None
    suggestion: str | None


@dataclass
class SchemaValidationResult:
    """Result of validating a single document against the schema."""
    doc_path: str
    issues: list[SchemaIssue] = field(default_factory=list)
    is_valid: bool = True


def _parse_frontmatter(content: str) -> tuple[dict | None, str]:
    """Extract YAML frontmatter and body from Markdown content."""
    if not content.startswith("---"):
        return None, content

    parts = content.split("---", 2)
    if len(parts) < 3:
        return None, content

    try:
        fm = yaml.safe_load(parts[1])
        body = parts[2].strip()
        return fm, body
    except yaml.YAMLError:
        return None, content


def validate_document(content: str, doc_path: str) -> SchemaValidationResult:
    """Validate a Markdown document against the canonical schema.

    Schema Rules:
    1. Frontmatter must exist with: title, description, source_url, fetched_at
    2. title: non-empty string, max 120 chars
    3. description: 50-300 char summary
    4. source_url: valid URL format
    5. fetched_at: ISO 8601 timestamp
    6. H1 must appear exactly once
    7. No skipped heading levels
    8. Code blocks must specify language
    9. No bare URLs in body
    10. Content between 200-8000 words
    """
    import uuid

    result = SchemaValidationResult(doc_path=doc_path)
    frontmatter, body = _parse_frontmatter(content)

    def add_issue(issue_type: str, severity: str, field_name: str | None,
                  message: str, line: int | None = None, suggestion: str | None = None):
        result.issues.append(SchemaIssue(
            issue_id=str(uuid.uuid4()),
            issue_type=issue_type,
            severity=severity,
            field=field_name,
            message=message,
            line=line,
            suggestion=suggestion,
        ))
        if severity == "critical":
            result.is_valid = False

    # --- Rule 1: Frontmatter must exist ---
    if frontmatter is None:
        add_issue("missing_frontmatter", "critical", None,
                  "Document has no YAML frontmatter block",
                  suggestion="Add a --- delimited YAML block at the top of the file")
        return result

    # --- Rule 2: title ---
    title = frontmatter.get("title")
    if not title:
        add_issue("missing_frontmatter", "critical", "title",
                  "Frontmatter key 'title' is missing or empty",
                  suggestion="Add: title: \"Your Document Title\"")
    elif len(str(title)) > 120:
        add_issue("invalid_frontmatter", "warning", "title",
                  f"Title exceeds 120 chars (currently {len(str(title))})",
                  suggestion="Shorten the title to 120 characters or fewer")

    # --- Rule 3: description ---
    desc = frontmatter.get("description")
    if not desc:
        add_issue("missing_frontmatter", "critical", "description",
                  "Frontmatter key 'description' is missing",
                  suggestion="Add: description: \"A 50-300 char summary\"")
    elif len(str(desc)) < 50:
        add_issue("invalid_frontmatter", "warning", "description",
                  f"Description too short ({len(str(desc))} chars, minimum 50)",
                  suggestion="Expand description to at least 50 characters")
    elif len(str(desc)) > 300:
        add_issue("invalid_frontmatter", "warning", "description",
                  f"Description too long ({len(str(desc))} chars, maximum 300)",
                  suggestion="Shorten description to 300 characters or fewer")

    # --- Rule 4: source_url ---
    source_url = frontmatter.get("source_url")
    if not source_url:
        add_issue("missing_frontmatter", "critical", "source_url",
                  "Frontmatter key 'source_url' is missing",
                  suggestion="Add: source_url: \"https://...\"")
    elif not str(source_url).startswith(("http://", "https://")):
        add_issue("invalid_frontmatter", "warning", "source_url",
                  "source_url does not start with http:// or https://",
                  suggestion="Provide a valid URL starting with https://")

    # --- Rule 5: fetched_at ---
    fetched_at = frontmatter.get("fetched_at")
    if not fetched_at:
        add_issue("missing_frontmatter", "warning", "fetched_at",
                  "Frontmatter key 'fetched_at' is missing",
                  suggestion="Add: fetched_at: \"2026-01-01T00:00:00Z\"")

    # --- Rule 6: Exactly one H1 ---
    h1_matches = re.findall(r"^# [^\n]+", body, re.MULTILINE)
    if len(h1_matches) == 0:
        add_issue("missing_heading", "warning", None,
                  "No H1 heading found in document body",
                  suggestion="Add a single # H1 heading at the top of the body")
    elif len(h1_matches) > 1:
        add_issue("multiple_h1", "warning", None,
                  f"Found {len(h1_matches)} H1 headings; should be exactly 1",
                  suggestion="Keep only one # H1 heading; demote others to ## H2")

    # --- Rule 7: No skipped heading levels ---
    headings = re.findall(r"^(#{1,6}) ", body, re.MULTILINE)
    levels = [len(h) for h in headings]
    for i in range(1, len(levels)):
        if levels[i] > levels[i - 1] + 1:
            line_num = None
            for ln_idx, line in enumerate(body.split("\n"), 1):
                if line.startswith("#" * levels[i] + " "):
                    line_num = ln_idx
                    break
            add_issue("skipped_heading_level", "warning", None,
                      f"Heading level skipped: H{levels[i-1]} -> H{levels[i]}",
                      line=line_num,
                      suggestion=f"Add an H{levels[i-1]+1} heading between them or adjust levels")
            break  # Report first occurrence only

    # --- Rule 8: Code blocks must specify language ---
    code_blocks = re.findall(r"^```(\w*)\s*$", body, re.MULTILINE)
    unlabeled = [i for i, lang in enumerate(code_blocks) if not lang]
    if unlabeled:
        add_issue("unlabeled_code_block", "warning", None,
                  f"Found {len(unlabeled)} code block(s) without language identifier",
                  suggestion="Add language after opening ```, e.g., ```python")

    # --- Rule 9: No bare URLs ---
    bare_url_pattern = r"(?<!\()(https?://[^\s\)]+)(?!\))"
    bare_urls = re.findall(bare_url_pattern, body)
    # Filter out URLs that are already in markdown link syntax
    md_links = re.findall(r"\[.*?\]\((https?://[^\)]+)\)", body)
    actual_bare = [u for u in bare_urls if u not in md_links]
    if actual_bare:
        add_issue("bare_url", "info", None,
                  f"Found {len(actual_bare)} bare URL(s) without descriptive anchor text",
                  suggestion="Wrap URLs in markdown link syntax: [description](url)")

    # --- Rule 10: Word count ---
    words = body.split()
    word_count = len(words)
    if word_count < 200:
        add_issue("content_too_short", "warning", None,
                  f"Document has only {word_count} words (minimum 200)",
                  suggestion="This document may need more content or be merged with another")
    elif word_count > 8000:
        add_issue("content_too_long", "info", None,
                  f"Document has {word_count} words (maximum 8000)",
                  suggestion="Consider splitting into smaller documents")

    return result
```

---

### Step 3: Create the LangGraph Audit Agent

**Working directory**: `rag-pipeline/apps/api/src/agents/`

#### 3.1 Create `audit_state.py` — Agent state definition

```python
"""State definition for the Audit Agent LangGraph workflow."""

from dataclasses import dataclass, field
from typing import TypedDict

from langgraph.graph import MessagesState


class AuditDocInfo(TypedDict):
    """Information about a single document being audited."""
    doc_id: str
    doc_path: str
    url: str
    title: str
    content: str
    issues: list[dict]
    quality_score: int
    status: str  # "pending" | "issues_found" | "approved"


class AuditState(TypedDict):
    """State for the Audit Agent graph."""
    job_id: str
    round: int
    documents: list[AuditDocInfo]
    total_issues: int
    summary: str
    report_id: str
    status: str  # "running" | "issues_found" | "approved"
```

#### 3.2 Create `audit_agent.py` — LangGraph workflow

```python
"""LangGraph Audit Agent — validates documents and generates audit reports."""

import json
import uuid
from pathlib import Path

from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, START, END

from src.agents.audit_state import AuditState, AuditDocInfo
from src.agents.schema_validator import validate_document

import structlog

logger = structlog.get_logger()

STAGING_DIR = Path("/app/data/staging")


# --- Node: load_documents ---
def load_documents(state: AuditState) -> dict:
    """Load all Markdown files from staging for this job."""
    job_dir = STAGING_DIR / state["job_id"] / "markdown"
    documents: list[AuditDocInfo] = []

    if not job_dir.exists():
        logger.error("staging_dir_not_found", job_id=state["job_id"])
        return {"documents": [], "status": "failed"}

    for md_file in sorted(job_dir.glob("*.md")):
        content = md_file.read_text(encoding="utf-8")
        documents.append(AuditDocInfo(
            doc_id=str(uuid.uuid4()),
            doc_path=str(md_file),
            url="",  # Will be extracted from frontmatter
            title=md_file.stem,
            content=content,
            issues=[],
            quality_score=0,
            status="pending",
        ))

    logger.info("documents_loaded", job_id=state["job_id"], count=len(documents))
    return {"documents": documents}


# --- Node: validate_schema ---
def validate_schema(state: AuditState) -> dict:
    """Run rule-based schema validation on all documents."""
    documents = state["documents"]

    for doc in documents:
        result = validate_document(doc["content"], doc["doc_path"])
        doc["issues"] = [
            {
                "id": issue.issue_id,
                "type": issue.issue_type,
                "severity": issue.severity,
                "field": issue.field,
                "message": issue.message,
                "line": issue.line,
                "suggestion": issue.suggestion,
            }
            for issue in result.issues
        ]
        doc["status"] = "approved" if result.is_valid else "issues_found"

    total_issues = sum(len(d["issues"]) for d in documents)
    logger.info("schema_validation_complete", total_issues=total_issues)
    return {"documents": documents, "total_issues": total_issues}


# --- Node: assess_quality (LLM) ---
async def assess_quality(state: AuditState) -> dict:
    """Use Claude to assess content quality: boilerplate, clarity, AI-readability."""
    llm = ChatAnthropic(model="claude-sonnet-4-20250514", max_tokens=2048, temperature=0)

    documents = state["documents"]

    for doc in documents:
        # Truncate content for token efficiency
        content_preview = doc["content"][:3000]

        prompt = f"""Assess the quality of this Markdown documentation for use in a RAG knowledge base.

Score from 0-100 on these criteria:
- Clarity: Is the content well-written and easy to understand?
- Completeness: Does it cover the topic adequately?
- AI-Readability: Will an LLM be able to use this effectively for RAG retrieval?
- Boilerplate: Does it contain cookie banners, navigation menus, or non-content noise?

Return ONLY a JSON object:
{{
  "quality_score": <0-100>,
  "boilerplate_detected": <true/false>,
  "issues": [
    {{
      "type": "boilerplate|low_clarity|incomplete|noise",
      "severity": "warning",
      "message": "<description>",
      "suggestion": "<how to fix>"
    }}
  ]
}}

Document:
{content_preview}"""

        try:
            response = await llm.ainvoke(prompt)
            content = response.content

            # Parse JSON from response
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            assessment = json.loads(content.strip())
            doc["quality_score"] = assessment.get("quality_score", 50)

            # Add LLM-detected issues
            for issue in assessment.get("issues", []):
                doc["issues"].append({
                    "id": str(uuid.uuid4()),
                    "type": issue.get("type", "quality"),
                    "severity": issue.get("severity", "warning"),
                    "field": None,
                    "message": issue.get("message", ""),
                    "line": None,
                    "suggestion": issue.get("suggestion", ""),
                })

            if doc["issues"]:
                doc["status"] = "issues_found"

        except Exception as e:
            logger.error("quality_assessment_failed", doc=doc["doc_path"], error=str(e))
            doc["quality_score"] = 50  # Default middle score on failure

    total_issues = sum(len(d["issues"]) for d in documents)
    return {"documents": documents, "total_issues": total_issues}


# --- Node: check_duplicates ---
def check_duplicates(state: AuditState) -> dict:
    """Check for near-duplicate documents using simple text similarity.

    NOTE: For production, replace with embedding-based cosine similarity.
    This uses a simplified Jaccard similarity for Phase 3.
    """
    documents = state["documents"]

    def jaccard_similarity(text1: str, text2: str) -> float:
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        if not words1 or not words2:
            return 0.0
        intersection = words1 & words2
        union = words1 | words2
        return len(intersection) / len(union)

    duplicate_threshold = 0.85

    for i in range(len(documents)):
        for j in range(i + 1, len(documents)):
            sim = jaccard_similarity(documents[i]["content"], documents[j]["content"])
            if sim >= duplicate_threshold:
                documents[j]["issues"].append({
                    "id": str(uuid.uuid4()),
                    "type": "near_duplicate",
                    "severity": "warning",
                    "field": None,
                    "message": f"Near-duplicate of {documents[i]['doc_path']} (similarity: {sim:.2f})",
                    "line": None,
                    "suggestion": "Consider removing this duplicate or merging content",
                })
                documents[j]["status"] = "issues_found"

    total_issues = sum(len(d["issues"]) for d in documents)
    return {"documents": documents, "total_issues": total_issues}


# --- Node: compile_report ---
def compile_report(state: AuditState) -> dict:
    """Compile all issues into a structured audit report."""
    documents = state["documents"]
    total_issues = sum(len(d["issues"]) for d in documents)
    docs_with_issues = sum(1 for d in documents if d["issues"])

    summary = (
        f"Audit Round {state['round']}: "
        f"Found {total_issues} issues across {docs_with_issues} of {len(documents)} documents."
    )

    status = "approved" if total_issues == 0 else "issues_found"

    logger.info(
        "report_compiled",
        job_id=state["job_id"],
        round=state["round"],
        total_issues=total_issues,
        status=status,
    )

    return {
        "total_issues": total_issues,
        "summary": summary,
        "status": status,
        "report_id": str(uuid.uuid4()),
    }


# --- Node: save_report ---
def save_report(state: AuditState) -> dict:
    """Save the audit report JSON to the staging directory."""
    job_dir = STAGING_DIR / state["job_id"]
    job_dir.mkdir(parents=True, exist_ok=True)

    report = {
        "job_id": state["job_id"],
        "round": state["round"],
        "report_id": state["report_id"],
        "total_issues": state["total_issues"],
        "summary": state["summary"],
        "status": state["status"],
        "documents": [
            {
                "doc_id": doc["doc_id"],
                "doc_path": doc["doc_path"],
                "url": doc["url"],
                "title": doc["title"],
                "issues": doc["issues"],
                "quality_score": doc["quality_score"],
                "status": doc["status"],
            }
            for doc in state["documents"]
        ],
    }

    report_path = job_dir / f"audit_report_round_{state['round']}.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    logger.info("report_saved", path=str(report_path))
    return {"status": state["status"]}


# --- Conditional edge ---
def should_approve(state: AuditState) -> str:
    """Determine next step: if zero issues, approve; otherwise, needs correction."""
    if state["total_issues"] == 0:
        return "approved"
    return "needs_correction"


# --- Build the graph ---
def build_audit_graph() -> StateGraph:
    """Construct the LangGraph audit agent workflow."""
    graph = StateGraph(AuditState)

    # Add nodes
    graph.add_node("load_documents", load_documents)
    graph.add_node("validate_schema", validate_schema)
    graph.add_node("assess_quality", assess_quality)
    graph.add_node("check_duplicates", check_duplicates)
    graph.add_node("compile_report", compile_report)
    graph.add_node("save_report", save_report)

    # Add edges
    graph.add_edge(START, "load_documents")
    graph.add_edge("load_documents", "validate_schema")
    graph.add_edge("validate_schema", "assess_quality")
    graph.add_edge("assess_quality", "check_duplicates")
    graph.add_edge("check_duplicates", "compile_report")
    graph.add_edge("compile_report", "save_report")
    graph.add_edge("save_report", END)

    return graph.compile()


# --- Entry point ---
async def run_audit(job_id: str, audit_round: int = 1) -> dict:
    """Run the audit agent on a job's staged documents.

    Returns the final state with report data.
    """
    graph = build_audit_graph()

    initial_state: AuditState = {
        "job_id": job_id,
        "round": audit_round,
        "documents": [],
        "total_issues": 0,
        "summary": "",
        "report_id": "",
        "status": "running",
    }

    result = await graph.ainvoke(initial_state)
    logger.info(
        "audit_complete",
        job_id=job_id,
        round=audit_round,
        status=result["status"],
        total_issues=result["total_issues"],
    )
    return result
```

---

## Files to Create/Modify

| Action | File Path |
|---|---|
| Modify | `rag-pipeline/apps/api/pyproject.toml` |
| Create | `rag-pipeline/apps/api/src/agents/schema_validator.py` |
| Create | `rag-pipeline/apps/api/src/agents/audit_state.py` |
| Create | `rag-pipeline/apps/api/src/agents/audit_agent.py` |

---

## Done-When Checklist

- [ ] `python -c "import langgraph, langchain, langchain_anthropic"` succeeds after dependency install
- [ ] Schema validator correctly detects: missing frontmatter, missing fields, multiple H1s, skipped heading levels, unlabeled code blocks, bare URLs, word count violations
- [ ] Calling `validate_document(markdown_content, path)` returns correctly identified issues on test documents
- [ ] LangGraph Audit Agent graph compiles and runs: load → validate → assess → duplicates → compile → save
- [ ] `await run_audit(job_id, round=1)` processes staged documents and saves a JSON report
- [ ] LLM quality assessment correctly flags boilerplate and low-quality content
- [ ] Duplicate detection identifies near-duplicate documents

---

## Summary Report

Upon completion of this subtask, create a summary report at:
`rag-pipeline/ai-workspace/summary-reports/phase-3-subtask-1-schema-validator-and-agent-summary.md`

The summary report must include:
- **Subtask**: Phase 3, Subtask 1 — Dependencies + Schema Validator + LangGraph Audit Agent
- **Status**: Complete / Partial / Blocked
- **Date**: {ISO 8601 date}
- **Files Created/Modified**: List every file path
- **Key Decisions**: Any deviations from the plan and why
- **Issues Encountered**: Problems and resolutions
- **Dependencies for Next Subtask**: What the next subtask needs to know
- **Verification Results**: Output of Done-When checklist items
