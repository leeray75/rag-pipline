"""A2A Protocol v1.0 server instances for Audit and Correction agents."""

from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore

from src.agents.a2a_audit_server import AuditTaskHandler
from src.agents.a2a_correction_server import CorrectionTaskHandler
from src.agents.a2a_agent_cards import build_audit_agent_card, build_correction_agent_card


def create_audit_server(base_url: str) -> DefaultRequestHandler:
    """Create and configure the Audit Agent server handler."""
    agent_card = build_audit_agent_card(base_url)
    handler = DefaultRequestHandler(
        agent_executor=AuditTaskHandler(),
        task_store=InMemoryTaskStore(),
        agent_card=agent_card,
    )
    return handler


def create_correction_server(base_url: str) -> DefaultRequestHandler:
    """Create and configure the Correction Agent server handler."""
    agent_card = build_correction_agent_card(base_url)
    handler = DefaultRequestHandler(
        agent_executor=CorrectionTaskHandler(),
        task_store=InMemoryTaskStore(),
        agent_card=agent_card,
    )
    return handler


def get_audit_routes(base_url: str):
    """Get the JSON-RPC routes for the Audit Agent."""
    handler = create_audit_server(base_url)
    return create_jsonrpc_routes(
        request_handler=handler,
        rpc_url="/a2a/audit",
        enable_v0_3_compat=False,
    )


def get_correction_routes(base_url: str):
    """Get the JSON-RPC routes for the Correction Agent."""
    handler = create_correction_server(base_url)
    return create_jsonrpc_routes(
        request_handler=handler,
        rpc_url="/a2a/correction",
        enable_v0_3_compat=False,
    )
