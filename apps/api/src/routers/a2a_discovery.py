"""A2A Protocol v1.0 — Agent discovery endpoints."""

import hashlib
import json

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from google.protobuf.json_format import MessageToDict

from src.agents.a2a_agent_cards import (
    build_audit_agent_card,
    build_correction_agent_card,
)

router = APIRouter()

BASE_URL = "http://localhost:8000"
A2A_VERSION = "1.0.2"


def _card_response(card) -> JSONResponse:
    """Create a JSON response for an AgentCard with proper headers."""
    content = MessageToDict(card, preserving_proto_field_name=True)
    # Ensure protocolVersion is present
    content.setdefault("protocolVersion", A2A_VERSION)
    etag = hashlib.md5(json.dumps(content, sort_keys=True).encode()).hexdigest()
    return JSONResponse(
        content=content,
        media_type="application/json",
        headers={
            "A2A-Version": A2A_VERSION,
            "Cache-Control": "public, max-age=3600",
            "ETag": f'"{etag}"',
        },
    )


@router.get("/a2a/audit/.well-known/agent-card.json")
async def audit_agent_card():
    """Serve the Audit Agent AgentCard for A2A discovery."""
    card = build_audit_agent_card(BASE_URL)
    return _card_response(card)


@router.get("/a2a/correction/.well-known/agent-card.json")
async def correction_agent_card():
    """Serve the Correction Agent AgentCard for A2A discovery."""
    card = build_correction_agent_card(BASE_URL)
    return _card_response(card)
