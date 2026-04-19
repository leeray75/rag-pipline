"""A2A Protocol v1.0 — Agent discovery endpoints."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from src.agents.a2a_agent_cards import (
    build_audit_agent_card,
    build_correction_agent_card,
)

router = APIRouter()

BASE_URL = "http://localhost:8000"


@router.get("/a2a/audit/.well-known/agent-card.json")
async def audit_agent_card():
    """Serve the Audit Agent AgentCard for A2A discovery."""
    card = build_audit_agent_card(BASE_URL)
    return JSONResponse(
        content=card.model_dump(),
        media_type="application/a2a+json",
        headers={"A2A-Version": "1.0"},
    )


@router.get("/a2a/correction/.well-known/agent-card.json")
async def correction_agent_card():
    """Serve the Correction Agent AgentCard for A2A discovery."""
    card = build_correction_agent_card(BASE_URL)
    return JSONResponse(
        content=card.model_dump(),
        media_type="application/a2a+json",
        headers={"A2A-Version": "1.0"},
    )
