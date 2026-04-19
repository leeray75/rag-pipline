"""LangGraph Audit Agent - 6-node workflow for document auditing.

This module implements a LangGraph workflow that performs comprehensive
document auditing including schema validation, LLM quality assessment,
and duplicate detection.
"""

import asyncio
import hashlib
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict

import structlog
# from langchain_anthropic import ChatAnthropic  # Using OpenAI-compatible endpoint instead
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from src.agents.audit_state import (
    AuditDocument,
    AuditReport,
    AuditState,
    DuplicateCheckResult,
    FrontmatterValidation,
    QualityScore,
)
from src.agents.schema_validator import SchemaValidator, ValidationSummary

logger = structlog.get_logger(__name__)

# Staging directory constant
STAGING_DIR = Path("/app/data/staging")


class AuditGraphState(TypedDict):
    """State schema for the LangGraph workflow."""
    state: AuditState
    current_doc_path: Optional[str]
    result: Optional[Dict[str, Any]]


class AuditAgent:
    """LangGraph-based audit agent with 6-node workflow.

    Workflow nodes:
    1. load_documents - Load documents from staging directory
    2. validate_schema - Validate Markdown schema and frontmatter
    3. assess_quality - Use Claude LLM for quality assessment
    4. check_duplicates - Detect near-duplicate documents
    5. compile_report - Compile final audit report
    6. save_report - Save report to disk
    """

    def __init__(
        self,
        anthropic_api_key: Optional[str] = None,
        openai_api_key: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """Initialize the audit agent.

        Args:
            anthropic_api_key: API key for Claude LLM (optional, deprecated)
            openai_api_key: API key for OpenAI LLM (optional)
            config: Additional configuration
        """
        self.config = config or {}
        self.staging_dir = Path(
            self.config.get("staging_dir", str(STAGING_DIR))
        )

        # Initialize LLMs
        self._init_llms(anthropic_api_key, openai_api_key)

        # Initialize schema validator
        self.validator = SchemaValidator()

        # Build the graph
        self.graph = self._build_graph()

    def _init_llms(
        self,
        anthropic_api_key: Optional[str],
        openai_api_key: Optional[str]
    ) -> None:
        """Initialize language models."""
        # OpenAI-compatible endpoint for quality assessment (replacement for Claude)
        self.claude = ChatOpenAI(
            base_url="http://spark-8013:4000/v1",
            model="qwen3-coder-next",
            api_key="not-needed",
            temperature=0.3,
            max_tokens=4096
        )
        logger.info("audit_agent.claude_initialized", model="qwen3-coder-next", endpoint="http://spark-8013:4000/v1")

        # OpenAI for other tasks (optional, used only if API key provided)
        openai_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        if openai_key:
            self.openai = ChatOpenAI(
                model_name="gpt-4o",
                api_key=openai_key,
                temperature=0.2,
            )
        else:
            self.openai = None
            logger.warning("audit_agent.openai_not_initialized", message="OPENAI_API_KEY not set")

        logger.info("audit_agent.llms_initialized")

    def _build_graph(self) -> StateGraph:
        """Build the 6-node workflow graph."""
        workflow = StateGraph(AuditGraphState)

        # Add nodes
        workflow.add_node("load_documents", self._load_documents)
        workflow.add_node("validate_schema", self._validate_schema)
        workflow.add_node("assess_quality", self._assess_quality)
        workflow.add_node("check_duplicates", self._check_duplicates)
        workflow.add_node("compile_report", self._compile_report)
        workflow.add_node("save_report", self._save_report)

        # Define edges
        workflow.add_edge("load_documents", "validate_schema")
        workflow.add_edge("validate_schema", "assess_quality")
        workflow.add_edge("assess_quality", "check_duplicates")
        workflow.add_edge("check_duplicates", "compile_report")
        workflow.add_edge("compile_report", "save_report")

        # Set entry point
        workflow.set_entry_point("load_documents")

        # Add conditional edge from save_report to next document or end
        workflow.add_conditional_edges(
            "save_report",
            self._should_continue,
            {
                "process_next": "load_documents",
                END: END,
            },
        )

        return workflow.compile()

    def _load_documents(self, state: AuditGraphState) -> AuditGraphState:
        """Load documents from the staging directory."""
        audit_state = state["state"]
        audit_state.started_at = datetime.utcnow()
        audit_state.status = "running"

        # Find all Markdown files in staging directory
        md_files = list(self.staging_dir.glob("**/*.md"))

        logger.info(
            "audit_agent.loading_documents",
            staging_dir=str(self.staging_dir),
            file_count=len(md_files)
        )

        for md_file in md_files:
            try:
                content = md_file.read_text(encoding="utf-8")
                doc = AuditDocument(
                    file_path=str(md_file),
                    content=content,
                    file_name=md_file.name,
                    file_extension=md_file.suffix,
                    file_size=md_file.stat().st_size,
                    created_at=datetime.fromtimestamp(md_file.stat().st_ctime),
                    modified_at=datetime.fromtimestamp(md_file.stat().st_mtime),
                )
                audit_state.add_document(doc)
                logger.info(
                    "audit_agent.document_loaded",
                    path=str(md_file),
                    size=md_file.stat().st_size
                )
            except Exception as e:
                audit_state.add_error(f"Failed to load {md_file}: {str(e)}")
                logger.error(
                    "audit_agent.document_load_error",
                    path=str(md_file),
                    error=str(e)
                )

        return {"state": audit_state}

    def _validate_schema(self, state: AuditGraphState) -> AuditGraphState:
        """Validate schema for all documents."""
        audit_state = state["state"]

        for i, doc in enumerate(audit_state.documents):
            audit_state.set_document_index(i)
            result = self.validator.validate_document(
                doc.content,
                doc.file_path
            )
            audit_state.validation_results[doc.file_path] = result

            # Create frontmatter validation result
            fm_validation = FrontmatterValidation(
                is_valid=result.frontmatter_valid,
                title=result.frontmatter.title if result.frontmatter else None,
                description=result.frontmatter.description if result.frontmatter else None,
                url=result.frontmatter.url if result.frontmatter else None,
                tags=result.frontmatter.tags if result.frontmatter else [],
                authors=result.frontmatter.authors if result.frontmatter else [],
                status=result.frontmatter.status if result.frontmatter else "unknown",
                errors=[
                    {"field": e.field, "message": e.message, "severity": e.severity}
                    for e in result.errors
                ]
            )
            audit_state.frontmatter_results[doc.file_path] = fm_validation

            logger.info(
                "audit_agent.schema_validation_complete",
                path=doc.file_path,
                is_valid=result.is_valid,
                word_count=result.word_count
            )

        return {"state": audit_state}

    async def _assess_quality(self, state: AuditGraphState) -> AuditGraphState:
        """Assess document quality using Claude LLM."""
        audit_state = state["state"]

        # Quality assessment prompt
        system_prompt = """You are a document quality assessment expert. Your task is to 
evaluate the quality of Markdown documents based on content quality, structure, and completeness.

Return a JSON response with the following structure:
{
    "overall_score": <float 0-100>,
    "content_quality": <float 0-100>,
    "structure_quality": <float 0-100>,
    "readability": <float 0-100>,
    "completeness": <float 0-100>,
    "confidence": <float 0-1>,
    "feedback": "<detailed assessment>",
    "suggestions": ["<suggestion 1>", "<suggestion 2>"]
}

Assessment criteria:
- Content Quality: Accuracy, relevance, depth of information
- Structure Quality: Headings hierarchy, organization, formatting
- Readability: Clarity, sentence structure, terminology
- Completeness: Coverage of topic, examples, supporting details
"""

        for i, doc in enumerate(audit_state.documents):
            audit_state.set_document_index(i)

            # Create user message with document content
            user_message = f"""Please assess the quality of this Markdown document:

Document Path: {doc.file_path}
Word Count: {audit_state.validation_results[doc.file_path].word_count}

Content:
{doc.content[:10000]}  # Limit to 10k chars for API

Please provide your assessment as JSON only (no markdown formatting)."""

            try:
                # Get quality assessment from Claude
                messages = [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_message),
                ]

                response = await self.claude.ainvoke(messages)
                response_text = response.content.strip()

                # Parse the response (handle possible markdown code blocks)
                if response_text.startswith("```json"):
                    response_text = response_text[7:-3].strip()
                elif response_text.startswith("```"):
                    response_text = response_text[3:-3].strip()

                # Parse JSON
                import json
                quality_data = json.loads(response_text)

                quality_score = QualityScore(
                    overall_score=float(quality_data.get("overall_score", 0)),
                    content_quality=float(quality_data.get("content_quality", 0)),
                    structure_quality=float(quality_data.get("structure_quality", 0)),
                    readability=float(quality_data.get("readability", 0)),
                    completeness=float(quality_data.get("completeness", 0)),
                    confidence=float(quality_data.get("confidence", 0)),
                    feedback=quality_data.get("feedback", ""),
                    suggestions=quality_data.get("suggestions", [])
                )

                audit_state.quality_scores[doc.file_path] = quality_score

                logger.info(
                    "audit_agent.quality_assessment_complete",
                    path=doc.file_path,
                    overall_score=quality_score.overall_score,
                    confidence=quality_score.confidence
                )

            except Exception as e:
                audit_state.add_error(f"Quality assessment failed for {doc.file_path}: {str(e)}")
                logger.error(
                    "audit_agent.quality_assessment_error",
                    path=doc.file_path,
                    error=str(e)
                )

                # Set default quality score on error
                audit_state.quality_scores[doc.file_path] = QualityScore(
                    overall_score=0,
                    content_quality=0,
                    structure_quality=0,
                    readability=0,
                    completeness=0,
                    confidence=0,
                    feedback=f"Assessment failed: {str(e)}",
                    suggestions=[]
                )

        return {"state": audit_state}

    def _check_duplicates(self, state: AuditGraphState) -> AuditGraphState:
        """Check for duplicate or near-duplicate documents."""
        audit_state = state["state"]
        documents = audit_state.documents

        for i, doc1 in enumerate(documents):
            for j, doc2 in enumerate(documents):
                if i >= j:
                    continue  # Skip self-comparison and duplicate comparisons

                # Compute similarity using simple hash-based approach
                # For production, use embeddings or more sophisticated algorithms
                hash1 = hashlib.md5(doc1.content.encode()).hexdigest()
                hash2 = hashlib.md5(doc2.content.encode()).hexdigest()

                # Exact match
                if hash1 == hash2:
                    result = DuplicateCheckResult(
                        is_duplicate=True,
                        duplicate_of=doc2.file_path,
                        similarity_score=1.0,
                        match_type="exact"
                    )
                    audit_state.duplicate_results[doc1.file_path] = result
                    logger.warning(
                        "audit_agent.exact_duplicate_found",
                        doc1=doc1.file_path,
                        doc2=doc2.file_path
                    )
                    continue

                # Near-duplicate detection (Jaccard similarity on n-grams)
                sim_score = self._calculate_ngram_similarity(
                    doc1.content,
                    doc2.content,
                    n=3
                )

                if sim_score > 0.8:  # 80% similarity threshold
                    result = DuplicateCheckResult(
                        is_duplicate=True,
                        duplicate_of=doc2.file_path,
                        similarity_score=sim_score,
                        match_type="near-duplicate"
                    )
                    audit_state.duplicate_results[doc1.file_path] = result
                    logger.warning(
                        "audit_agent.near_duplicate_found",
                        doc1=doc1.file_path,
                        doc2=doc2.file_path,
                        similarity=sim_score
                    )

        return {"state": audit_state}

    def _calculate_ngram_similarity(self, text1: str, text2: str, n: int = 3) -> float:
        """Calculate Jaccard similarity based on n-grams."""
        # Normalize and extract n-grams
        def get_ngrams(text: str) -> set:
            text = text.lower()
            text = "".join(c for c in text if c.isalnum() or c.isspace())
            words = text.split()
            ngrams = set()
            for i in range(len(words) - n + 1):
                ngrams.add(" ".join(words[i:i+n]))
            return ngrams

        ngrams1 = get_ngrams(text1)
        ngrams2 = get_ngrams(text2)

        if not ngrams1 or not ngrams2:
            return 0.0

        intersection = len(ngrams1 & ngrams2)
        union = len(ngrams1 | ngrams2)

        return intersection / union if union > 0 else 0.0

    def _compile_report(self, state: AuditGraphState) -> AuditGraphState:
        """Compile final audit report for each document."""
        audit_state = state["state"]

        for doc in audit_state.documents:
            validation = audit_state.validation_results.get(doc.file_path)
            quality = audit_state.quality_scores.get(doc.file_path)
            fm_validation = audit_state.frontmatter_results.get(doc.file_path)
            duplicate = audit_state.duplicate_results.get(doc.file_path)

            # Determine overall status
            critical_issues = []
            warnings = []
            recommendations = []
            notes = []

            # Check for critical errors
            if validation:
                critical_issues.extend([e.message for e in validation.errors if e.severity == "error"])
                warnings.extend([e.message for e in validation.errors if e.severity == "warning"])
                recommendations.extend([e.message for e in validation.errors])

            if duplicate and duplicate.is_duplicate:
                critical_issues.append(f"Duplicate of: {duplicate.duplicate_of}")

            if quality:
                recommendations.extend(quality.suggestions)
                if quality.confidence < 0.7:
                    notes.append(f"Quality assessment confidence is low ({quality.confidence})")

            # Determine approval status
            if len(critical_issues) == 0 and quality and quality.overall_score >= 70:
                approval_status = "approved"
                overall_status = "approved"
            else:
                approval_status = "needs_correction"
                overall_status = "needs_correction"

            audit_state.approval_status = approval_status

            # Create report
            report = AuditReport(
                document_path=doc.file_path,
                overall_status=overall_status,
                timestamp=datetime.utcnow(),
                validation=validation,
                frontmatter=fm_validation,
                quality=quality,
                duplicates=list(audit_state.duplicate_results.values()) if audit_state.duplicate_results else None,
                word_count=validation.word_count if validation else 0,
                recommendations=recommendations,
                critical_issues=critical_issues,
                warnings=warnings,
                notes=notes
            )

            audit_state.set_report(doc.file_path, report)

            logger.info(
                "audit_agent.report_compiled",
                path=doc.file_path,
                status=overall_status,
                score=quality.overall_score if quality else 0,
                issue_count=len(critical_issues)
            )

        return {"state": audit_state}

    def _save_report(self, state: AuditGraphState) -> AuditGraphState:
        """Save audit report to disk."""
        audit_state = state["state"]
        reports_dir = Path(self.config.get("reports_dir", "/app/data/reports"))
        reports_dir.mkdir(parents=True, exist_ok=True)

        for doc in audit_state.documents:
            report = audit_state.get_report(doc.file_path)
            if report:
                # Generate report filename
                filename = f"audit_{Path(doc.file_path).stem}_{report.timestamp.strftime('%Y%m%d_%H%M%S')}.json"
                report_path = reports_dir / filename

                # Serialize report to JSON
                report_data = report.model_dump(mode="json")

                # Save report
                report_path.write_text(
                    report.model_dump_json(indent=2),
                    encoding="utf-8"
                )

                logger.info(
                    "audit_agent.report_saved",
                    path=str(report_path),
                    status=report.overall_status
                )

        return {"state": audit_state}

    def _should_continue(self, state: AuditGraphState) -> str:
        """Conditional edge to determine if there are more documents to process."""
        audit_state = state["state"]

        if audit_state.current_document_index + 1 < len(audit_state.documents):
            return "process_next"
        return END


async def run_audit(
    documents: Optional[List[str]] = None,
    staging_dir: Optional[str] = None,
    anthropic_api_key: Optional[str] = None,
    openai_api_key: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None
) -> AuditState:
    """Run the complete audit workflow.

    Args:
        documents: Optional list of document paths to audit
        staging_dir: Directory containing documents to audit
        anthropic_api_key: API key for Claude LLM
        openai_api_key: API key for OpenAI LLM
        config: Additional configuration

    Returns:
        The final audit state with all results
    """
    # Determine staging directory
    actual_staging_dir = staging_dir or str(STAGING_DIR)

    # Initialize agent
    agent = AuditAgent(
        anthropic_api_key=anthropic_api_key,
        openai_api_key=openai_api_key,
        config=config or {"staging_dir": actual_staging_dir}
    )

    # Create initial state
    initial_state = AuditGraphState(
        state=AuditState(),
        current_doc_path=None,
        result=None
    )

    # Run the workflow
    final_state = await agent.graph.ainvoke(initial_state)

    return final_state["state"]


# Convenience function for synchronous usage
def run_audit_sync(
    documents: Optional[List[str]] = None,
    staging_dir: Optional[str] = None,
    anthropic_api_key: Optional[str] = None,
    openai_api_key: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None
) -> AuditState:
    """Synchronous wrapper for run_audit."""
    return asyncio.run(
        run_audit(
            documents=documents,
            staging_dir=staging_dir,
            anthropic_api_key=anthropic_api_key,
            openai_api_key=openai_api_key,
            config=config
        )
    )
