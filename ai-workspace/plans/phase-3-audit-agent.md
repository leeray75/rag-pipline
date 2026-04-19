# Phase 3 — Audit Agent: Schema Validation & Report Generation

> **Prerequisites**: Phase 2 complete — crawl pipeline produces Markdown files with frontmatter in staging directories, API endpoints for jobs/documents work, Celery task chain runs.
> **Ref**: [phase-0-index.md](phase-0-index.md) for pinned versions.

---

## Objective

Build a LangGraph Audit Agent that validates all Markdown documents against a content schema, assesses quality using an LLM, checks for duplicates, and produces a structured JSON audit report. Store reports in Postgres and expose them via API endpoints with a dashboard viewer.

---

## Task 1: Add Phase 3 Python Dependencies

**Working directory**: `rag-pipeline/apps/api/`

### 1.1 Update `pyproject.toml` — add to `[project.dependencies]`

```toml
    "langgraph>=1.1.0",
    "langchain>=1.2.0",
    "langchain-anthropic>=0.4.0",
    "langchain-openai>=0.3.0",
    "pydantic-ai>=0.1.0",
    "numpy>=2.0.0",
```

### 1.2 Install

```bash
pip install -e ".[dev]"
```

**Done when**: `python -c "import langgraph, langchain, langchain_anthropic"` succeeds.

---

## Task 2: Define the Document Schema Validator

**Working directory**: `rag-pipeline/apps/api/src/agents/`

### 2.1 Create `schema_validator.py`

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

**Done when**: Calling `validate_document(markdown_content, path)` returns correctly identified issues on test documents.

---

## Task 3: Build the LangGraph Audit Agent

**Working directory**: `rag-pipeline/apps/api/src/agents/`

### 3.1 Create `audit_state.py` — Agent state definition

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

### 3.2 Create `audit_agent.py` — LangGraph workflow

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

**Done when**: `await run_audit(job_id, round=1)` processes staged documents and outputs a JSON audit report.

---

## Task 4: Build Audit API Endpoints

**Working directory**: `rag-pipeline/apps/api/src/routers/`

### 4.1 Create `audit.py`

```python
"""API routes for audit reports and triggering audits."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.models import AuditReport, IngestionJob, JobStatus
from src.agents.audit_agent import run_audit

import structlog

logger = structlog.get_logger()

router = APIRouter()


@router.post("/jobs/{job_id}/audit", status_code=202)
async def trigger_audit(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Trigger an audit on a job's staged documents."""
    result = await db.execute(select(IngestionJob).where(IngestionJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Determine round number
    next_round = job.current_audit_round + 1

    # Update job status
    job.status = JobStatus.AUDITING
    job.current_audit_round = next_round
    await db.commit()

    # Run audit agent
    audit_result = await run_audit(str(job_id), audit_round=next_round)

    # Save report to Postgres
    report = AuditReport(
        job_id=job_id,
        round=next_round,
        total_issues=audit_result["total_issues"],
        issues_json={
            "documents": [
                {
                    "doc_id": doc["doc_id"],
                    "issues": doc["issues"],
                    "quality_score": doc["quality_score"],
                    "status": doc["status"],
                }
                for doc in audit_result["documents"]
            ]
        },
        summary=audit_result["summary"],
        status=audit_result["status"],
    )
    db.add(report)

    # Update job status based on result
    if audit_result["status"] == "approved":
        job.status = JobStatus.REVIEW  # Goes to human review
    else:
        job.status = JobStatus.AUDITING

    await db.commit()
    await db.refresh(report)

    return {
        "report_id": str(report.id),
        "round": next_round,
        "total_issues": audit_result["total_issues"],
        "summary": audit_result["summary"],
        "status": audit_result["status"],
    }


@router.get("/jobs/{job_id}/audit-reports")
async def list_audit_reports(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """List all audit reports for a job."""
    result = await db.execute(
        select(AuditReport)
        .where(AuditReport.job_id == job_id)
        .order_by(AuditReport.round)
    )
    reports = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "round": r.round,
            "total_issues": r.total_issues,
            "summary": r.summary,
            "status": r.status,
            "created_at": r.created_at.isoformat(),
        }
        for r in reports
    ]


@router.get("/jobs/{job_id}/audit-reports/{report_id}")
async def get_audit_report(
    job_id: uuid.UUID, report_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    """Get a full audit report with per-document issues."""
    result = await db.execute(
        select(AuditReport).where(
            AuditReport.id == report_id, AuditReport.job_id == job_id
        )
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    return {
        "id": str(report.id),
        "job_id": str(report.job_id),
        "round": report.round,
        "total_issues": report.total_issues,
        "issues_json": report.issues_json,
        "summary": report.summary,
        "status": report.status,
        "agent_notes": report.agent_notes,
        "created_at": report.created_at.isoformat(),
    }
```

### 4.2 Register the audit router in `src/main.py`

Add to imports and router registration:

```python
from src.routers import health, jobs, websocket, audit

app.include_router(audit.router, prefix="/api/v1", tags=["audit"])
```

**Done when**: `POST /api/v1/jobs/{id}/audit` triggers the audit agent and returns a report summary.

---

## Task 5: Build Audit Report Viewer UI

**Working directory**: `rag-pipeline/apps/web/`

### 5.1 Create RTK Query endpoints — `src/store/api/audit-api.ts`

```typescript
import { apiSlice } from "./api-slice";

export interface AuditReportSummary {
  id: string;
  round: number;
  total_issues: number;
  summary: string;
  status: string;
  created_at: string;
}

export interface AuditIssue {
  id: string;
  type: string;
  severity: "critical" | "warning" | "info";
  field: string | null;
  message: string;
  line: number | null;
  suggestion: string | null;
}

export interface AuditDocResult {
  doc_id: string;
  issues: AuditIssue[];
  quality_score: number;
  status: string;
}

export interface AuditReportDetail extends AuditReportSummary {
  job_id: string;
  issues_json: { documents: AuditDocResult[] };
  agent_notes: string | null;
}

export const auditApi = apiSlice.injectEndpoints({
  endpoints: (builder) => ({
    triggerAudit: builder.mutation<AuditReportSummary, string>({
      query: (jobId) => ({ url: `/jobs/${jobId}/audit`, method: "POST" }),
      invalidatesTags: ["AuditReports"],
    }),
    listAuditReports: builder.query<AuditReportSummary[], string>({
      query: (jobId) => `/jobs/${jobId}/audit-reports`,
      providesTags: ["AuditReports"],
    }),
    getAuditReport: builder.query<AuditReportDetail, { jobId: string; reportId: string }>({
      query: ({ jobId, reportId }) => `/jobs/${jobId}/audit-reports/${reportId}`,
    }),
  }),
});

export const {
  useTriggerAuditMutation,
  useListAuditReportsQuery,
  useGetAuditReportQuery,
} = auditApi;
```

### 5.2 Create Audit Report page — `src/app/audit/[jobId]/page.tsx`

```tsx
"use client";

import { use } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
  useListAuditReportsQuery,
  useGetAuditReportQuery,
  useTriggerAuditMutation,
  type AuditIssue,
} from "@/store/api/audit-api";
import { useState } from "react";

function severityColor(severity: string): "default" | "destructive" | "secondary" {
  switch (severity) {
    case "critical": return "destructive";
    case "warning": return "default";
    default: return "secondary";
  }
}

export default function AuditPage({ params }: { params: Promise<{ jobId: string }> }) {
  const { jobId } = use(params);
  const [selectedReportId, setSelectedReportId] = useState<string | null>(null);
  const { data: reports } = useListAuditReportsQuery(jobId);
  const { data: reportDetail } = useGetAuditReportQuery(
    { jobId, reportId: selectedReportId! },
    { skip: !selectedReportId }
  );
  const [triggerAudit, { isLoading: isAuditing }] = useTriggerAuditMutation();

  return (
    <main className="container mx-auto p-8">
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-3xl font-bold">Audit Reports</h1>
        <Button onClick={() => triggerAudit(jobId)} disabled={isAuditing}>
          {isAuditing ? "Running Audit..." : "Run Audit"}
        </Button>
      </div>

      {/* Report List */}
      <div className="grid grid-cols-12 gap-6">
        <div className="col-span-4 space-y-3">
          {reports?.map((report) => (
            <Card
              key={report.id}
              className={`cursor-pointer ${selectedReportId === report.id ? "border-primary" : ""}`}
              onClick={() => setSelectedReportId(report.id)}
            >
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center justify-between">
                  Round {report.round}
                  <Badge variant={report.status === "approved" ? "default" : "destructive"}>
                    {report.status === "approved" ? "Clean" : `${report.total_issues} issues`}
                  </Badge>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-xs text-muted-foreground">{report.summary}</p>
              </CardContent>
            </Card>
          ))}
          {!reports?.length && (
            <p className="text-muted-foreground text-sm">No audit reports yet. Click Run Audit above.</p>
          )}
        </div>

        {/* Report Detail */}
        <div className="col-span-8">
          {reportDetail ? (
            <Card>
              <CardHeader>
                <CardTitle>Round {reportDetail.round} Report</CardTitle>
                <p className="text-sm text-muted-foreground">{reportDetail.summary}</p>
              </CardHeader>
              <CardContent className="space-y-6">
                {reportDetail.issues_json?.documents?.map((doc) => (
                  <div key={doc.doc_id}>
                    <div className="flex items-center justify-between mb-2">
                      <h4 className="font-medium text-sm">{doc.doc_id}</h4>
                      <div className="flex items-center gap-2">
                        <Badge variant="secondary">Score: {doc.quality_score}</Badge>
                        <Badge variant={doc.issues.length === 0 ? "default" : "destructive"}>
                          {doc.issues.length} issues
                        </Badge>
                      </div>
                    </div>
                    {doc.issues.map((issue: AuditIssue) => (
                      <div key={issue.id} className="ml-4 p-3 border rounded mb-2">
                        <div className="flex items-center gap-2 mb-1">
                          <Badge variant={severityColor(issue.severity)}>{issue.severity}</Badge>
                          <span className="text-xs font-mono">{issue.type}</span>
                          {issue.field && (
                            <span className="text-xs text-muted-foreground">field: {issue.field}</span>
                          )}
                        </div>
                        <p className="text-sm">{issue.message}</p>
                        {issue.suggestion && (
                          <p className="text-xs text-muted-foreground mt-1">
                            💡 {issue.suggestion}
                          </p>
                        )}
                      </div>
                    ))}
                    <Separator className="mt-4" />
                  </div>
                ))}
              </CardContent>
            </Card>
          ) : (
            <div className="flex items-center justify-center h-64 border rounded-lg">
              <p className="text-muted-foreground">Select an audit report to view details</p>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
```

### 5.3 Add navigation link

In `src/app/layout.tsx`, add to the nav bar:

```tsx
<a href="/audit" className="text-sm hover:underline">Audit</a>
```

**Done when**: The `/audit/{jobId}` page renders audit reports with per-document issues grouped by severity.

---

## Task 6: Write Phase 3 Tests

**Working directory**: `rag-pipeline/apps/api/`

### 6.1 Create `tests/test_schema_validator.py`

```python
"""Tests for the rule-based schema validator."""

from src.agents.schema_validator import validate_document


def test_valid_document_passes():
    """A well-formed document should have zero critical issues."""
    content = """---
title: "Getting Started with MCP"
description: "A comprehensive guide to the Model Context Protocol for beginners and intermediate developers"
source_url: "https://modelcontextprotocol.io/docs/getting-started"
fetched_at: "2026-01-01T00:00:00Z"
tags: ["mcp", "protocol"]
---

# Getting Started with MCP

This is a comprehensive guide to understanding the Model Context Protocol.

""" + "Content paragraph. " * 50  # Ensure > 200 words

    result = validate_document(content, "test.md")
    critical_issues = [i for i in result.issues if i.severity == "critical"]
    assert len(critical_issues) == 0
    assert result.is_valid is True


def test_missing_frontmatter_is_critical():
    """Document without frontmatter should have a critical issue."""
    content = "# No Frontmatter\n\nJust body content here."
    result = validate_document(content, "test.md")
    assert result.is_valid is False
    assert any(i.issue_type == "missing_frontmatter" for i in result.issues)


def test_missing_title_is_critical():
    """Missing title in frontmatter should be critical."""
    content = """---
description: "A valid description that is at least fifty characters long for testing"
source_url: "https://example.com"
fetched_at: "2026-01-01T00:00:00Z"
---

# Heading

Content here.
"""
    result = validate_document(content, "test.md")
    assert any(
        i.issue_type == "missing_frontmatter" and i.field == "title"
        for i in result.issues
    )


def test_multiple_h1_detected():
    """Multiple H1 headings should generate a warning."""
    content = """---
title: "Test"
description: "A valid description that is at least fifty characters long for testing"
source_url: "https://example.com"
fetched_at: "2026-01-01T00:00:00Z"
---

# First H1

Some content.

# Second H1

More content.
""" + "Word " * 200
    result = validate_document(content, "test.md")
    assert any(i.issue_type == "multiple_h1" for i in result.issues)


def test_skipped_heading_level():
    """H1 -> H3 skip should be detected."""
    content = """---
title: "Test"
description: "A valid description that is at least fifty characters long for testing"
source_url: "https://example.com"
fetched_at: "2026-01-01T00:00:00Z"
---

# Main Title

### Skipped to H3

Content.
""" + "Word " * 200
    result = validate_document(content, "test.md")
    assert any(i.issue_type == "skipped_heading_level" for i in result.issues)


def test_unlabeled_code_block():
    """Code blocks without language identifiers should be flagged."""
    content = """---
title: "Test"
description: "A valid description that is at least fifty characters long for testing"
source_url: "https://example.com"
fetched_at: "2026-01-01T00:00:00Z"
---

# Title

```
some code without language
```
""" + "Word " * 200
    result = validate_document(content, "test.md")
    assert any(i.issue_type == "unlabeled_code_block" for i in result.issues)


def test_short_content_warning():
    """Documents under 200 words should get a warning."""
    content = """---
title: "Test"
description: "A valid description that is at least fifty characters long for testing"
source_url: "https://example.com"
fetched_at: "2026-01-01T00:00:00Z"
---

# Title

Short content.
"""
    result = validate_document(content, "test.md")
    assert any(i.issue_type == "content_too_short" for i in result.issues)
```

**Done when**: `pytest tests/test_schema_validator.py -v` passes all 6 tests.

---

## Phase 3 Done-When Checklist

- [ ] Schema validator correctly detects: missing frontmatter, missing fields, multiple H1s, skipped heading levels, unlabeled code blocks, bare URLs, word count violations
- [ ] LangGraph Audit Agent graph compiles and runs: load → validate → assess → duplicates → compile → save
- [ ] `await run_audit(job_id, round=1)` processes staged documents and saves a JSON report
- [ ] `POST /api/v1/jobs/{id}/audit` triggers the agent and returns a report summary
- [ ] `GET /api/v1/jobs/{id}/audit-reports` returns list of reports ordered by round
- [ ] `GET /api/v1/jobs/{id}/audit-reports/{report_id}` returns full report with per-document issues
- [ ] Audit Report viewer page renders issues grouped by document and severity
- [ ] LLM quality assessment correctly flags boilerplate and low-quality content
- [ ] Duplicate detection identifies near-duplicate documents
- [ ] `pytest tests/test_schema_validator.py -v` passes all tests
