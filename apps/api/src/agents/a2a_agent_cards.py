"""A2A Protocol v1.0 — Agent Card definitions for Audit and Correction agents."""

from a2a.types import AgentCard, AgentSkill, AgentCapabilities

# Use the lowercase string values directly for modes
INPUT_MODES_JSON = ["application/json"]
OUTPUT_MODES_JSON = ["application/json"]


def build_audit_agent_card(base_url: str) -> AgentCard:
    """Build the AgentCard for the Audit Agent."""
    return AgentCard(
        name="RAG Pipeline Audit Agent",
        description="Validates Markdown documents against a 10-rule schema. "
        "Produces structured audit reports with issue classifications.",
        url=f"{base_url}/a2a/audit",
        version="1.0.0",
        default_input_modes=INPUT_MODES_JSON,
        default_output_modes=OUTPUT_MODES_JSON,
        capabilities=AgentCapabilities(streaming=True, pushNotifications=False),
        skills=[
            AgentSkill(
                id="audit-documents",
                name="Audit Documents",
                description="Run schema validation and quality audit on staged Markdown documents.",
                tags=["audit", "validation", "markdown", "quality"],
                examples=["Audit all documents for job abc-123"],
                input_modes=INPUT_MODES_JSON,
                output_modes=OUTPUT_MODES_JSON,
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
        default_input_modes=INPUT_MODES_JSON,
        default_output_modes=OUTPUT_MODES_JSON,
        capabilities=AgentCapabilities(streaming=True, pushNotifications=False),
        skills=[
            AgentSkill(
                id="correct-documents",
                name="Correct Documents",
                description="Classify audit issues and apply corrections to Markdown documents.",
                tags=["correction", "markdown", "llm", "classification"],
                examples=["Correct documents based on audit report rpt-456"],
                input_modes=INPUT_MODES_JSON,
                output_modes=OUTPUT_MODES_JSON,
            ),
        ],
    )
