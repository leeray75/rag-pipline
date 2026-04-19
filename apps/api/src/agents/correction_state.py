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
