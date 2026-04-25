"""RAG Pipeline API — main entry point."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded

from src.config import settings
from src.logging_config import configure_logging
from src.mcp.http_transport import mcp_lifespan, mcp_starlette_app
from src.routers import (
    auth,
    health,
    jobs,
    websocket,
    audit,
    loop,
    a2a_discovery,
    review,
    ingest,
)
from src.rate_limit import limiter, rate_limit_exceeded_handler
from src.telemetry import configure_telemetry
from src.metrics import configure_metrics
from src.agents.a2a_servers import get_audit_routes, get_correction_routes

# Configure structured logging before app creation
configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler — startup and shutdown.

    Starts the MCP Streamable HTTP session manager and A2A servers alongside the FastAPI app
    so that the session manager task group is active for the full server lifetime.
    """
    # Create and mount A2A server routes
    base_url = settings.a2a_base_url
    audit_routes = get_audit_routes(base_url)
    correction_routes = get_correction_routes(base_url)

    # Mount the routes at /a2a/audit and /a2a/correction
    for route in audit_routes:
        app.router.routes.append(route)
    for route in correction_routes:
        app.router.routes.append(route)

    async with mcp_lifespan():
        yield


app = FastAPI(
    title="RAG Pipeline API",
    description="AI Knowledge Base RAG Ingestion Pipeline",
    version="0.1.0",
    lifespan=lifespan,
)

# Configure OpenTelemetry distributed tracing
configure_telemetry(app)

# Configure Prometheus metrics
configure_metrics(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(jobs.router, prefix="/api/v1", tags=["jobs"])
app.include_router(websocket.router, prefix="/api/v1/ws", tags=["websocket"])
app.include_router(audit.router, prefix="/api/v1", tags=["audit"])
app.include_router(loop.router, prefix="/api/v1", tags=["loop"])
app.include_router(a2a_discovery.router, tags=["a2a-discovery"])
app.include_router(review.router, prefix="/api/v1", tags=["review"])
app.include_router(ingest.router, prefix="/api/v1", tags=["ingest"])

# Include auth router for /api/v1/auth/login endpoint
app.include_router(auth.router, prefix="/api/v1", tags=["auth"])

# Configure rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# Mount the MCP Streamable HTTP ASGI app.
# FastMCP registers its route at "/mcp" internally, so we mount at "/"
# to let the Starlette sub-app handle the full path.
# Clients connect to: POST http://localhost:8000/mcp
app.mount("/", mcp_starlette_app)
