"""State definitions for the LangGraph Audit Agent.

This module defines the state structures used throughout the audit workflow,
including document metadata, validation results, LLM assessments, and reports.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from src.agents.schema_validator import ValidationSummary


class AuditDocument(BaseModel):
    """Represents a single document being audited."""
    file_path: str
    content: str
    file_name: str
    file_extension: str
    file_size: int
    created_at: Optional[datetime] = None
    modified_at: Optional[datetime] = None


class FrontmatterValidation(BaseModel):
    """Results of frontmatter validation."""
    is_valid: bool
    title: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    authors: List[str] = Field(default_factory=list)
    status: str = "unknown"
    errors: List[Dict[str, Any]] = Field(default_factory=list)


class QualityScore(BaseModel):
    """LLM-generated quality assessment score."""
    overall_score: float = Field(ge=0, le=100)
    content_quality: float = Field(ge=0, le=100)
    structure_quality: float = Field(ge=0, le=100)
    readability: float = Field(ge=0, le=100)
    completeness: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    feedback: str = ""
    suggestions: List[str] = Field(default_factory=list)


class DuplicateCheckResult(BaseModel):
    """Results of duplicate document checking."""
    is_duplicate: bool = False
    duplicate_of: Optional[str] = None
    similarity_score: float = Field(default=0.0, ge=0, le=1)
    match_type: str = "none"  # "none", "exact", "near-duplicate", "similar-content"


class AuditReport(BaseModel):
    """Final audit report with all findings."""
    document_path: str
    overall_status: str = "pending"  # "pending", "approved", "needs_correction"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    validation: Optional[ValidationSummary] = None
    frontmatter: Optional[FrontmatterValidation] = None
    quality: Optional[QualityScore] = None
    duplicates: Optional[List[DuplicateCheckResult]] = None
    word_count: int = 0
    recommendations: List[str] = Field(default_factory=list)
    critical_issues: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


class AuditState(BaseModel):
    """State container for the audit workflow.

    This state is passed through all nodes in the LangGraph workflow,
    accumulating results and metadata as the audit progresses.
    """
    # Document source
    documents: List[AuditDocument] = Field(default_factory=list)
    document_paths: List[str] = Field(default_factory=list)

    # Current working document
    current_document: Optional[AuditDocument] = None
    current_document_index: int = 0

    # Validation results
    validation_results: Dict[str, ValidationSummary] = Field(default_factory=dict)

    # Frontmatter validation
    frontmatter_results: Dict[str, FrontmatterValidation] = Field(default_factory=dict)

    # Quality assessments (from LLM)
    quality_scores: Dict[str, QualityScore] = Field(default_factory=dict)

    # Duplicate detection results
    duplicate_results: Dict[str, DuplicateCheckResult] = Field(default_factory=dict)

    # Final reports
    reports: Dict[str, AuditReport] = Field(default_factory=dict)

    # Workflow metadata
    workflow_id: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: str = "pending"  # "pending", "running", "completed", "failed"
    errors: List[str] = Field(default_factory=list)

    # Audit configuration
    config: Dict[str, Any] = Field(default_factory=dict)

    # Approval state (for conditional edges)
    approval_status: Optional[str] = None  # "approved", "needs_correction", "rejected"

    def get_current_document(self) -> AuditDocument:
        """Get the current document or raise an error."""
        if self.current_document is None:
            raise ValueError("No current document set")
        return self.current_document

    def add_document(self, doc: AuditDocument) -> None:
        """Add a document to the audit queue."""
        self.documents.append(doc)
        self.document_paths.append(doc.file_path)

    def set_document_index(self, index: int) -> None:
        """Set the current document by index."""
        if 0 <= index < len(self.documents):
            self.current_document = self.documents[index]
            self.current_document_index = index

    def get_report(self, doc_path: str) -> Optional[AuditReport]:
        """Get the audit report for a document."""
        return self.reports.get(doc_path)

    def set_report(self, doc_path: str, report: AuditReport) -> None:
        """Set the audit report for a document."""
        self.reports[doc_path] = report

    def update_status(self, new_status: str) -> None:
        """Update the workflow status."""
        self.status = new_status
        if new_status == "completed":
            self.completed_at = datetime.utcnow()

    def add_error(self, error: str) -> None:
        """Add an error to the workflow."""
        self.errors.append(error)
        self.status = "failed"

    def to_dict(self) -> Dict[str, Any]:
        """Convert state to a dictionary (for serialization)."""
        return {
            "workflow_id": self.workflow_id,
            "status": self.status,
            "document_count": len(self.documents),
            "report_count": len(self.reports),
            "errors": self.errors,
            "approval_status": self.approval_status,
        }
