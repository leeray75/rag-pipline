"""LangGraph Correction Agent — classifies issues and applies corrections."""

import json
from pathlib import Path

from langchain_openai import ChatOpenAI
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
    """Use Qwen to classify each issue as LEGITIMATE or FALSE_POSITIVE."""
    llm = ChatOpenAI(
        base_url="http://spark-8013:4000/v1",
        model="qwen3-coder-next",
        api_key="not-needed",
        max_tokens=2048,
        temperature=0
    )
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
    llm = ChatOpenAI(
        base_url="http://spark-8013:4000/v1",
        model="qwen3-coder-next",
        api_key="not-needed",
        max_tokens=4096,
        temperature=0
    )
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
