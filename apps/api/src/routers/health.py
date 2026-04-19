"""Health check endpoints for Docker and load balancer probing."""

import logging
import os

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    """Basic liveness check — always returns 200 if the process is running."""
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness(db: AsyncSession = Depends(get_db)):
    """Readiness check — verifies Postgres, Redis, and Qdrant connectivity.

    Returns 200 only if all dependencies are reachable.
    """
    checks = {}

    # Postgres
    try:
        await db.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception as e:
        checks["postgres"] = f"error: {e}"

    # Redis
    try:
        from src.workers.celery_app import celery_app

        celery_app.control.ping(timeout=2)
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {e}"

    # Qdrant
    try:
        from qdrant_client import QdrantClient

        client = QdrantClient(url=os.getenv("QDRANT_URL", "http://localhost:6333"))
        client.get_collections()
        checks["qdrant"] = "ok"
    except Exception as e:
        checks["qdrant"] = f"error: {e}"

    all_ok = all(v == "ok" for v in checks.values())
    status_code = 200 if all_ok else 503

    from starlette.responses import JSONResponse

    return JSONResponse(
        status_code=status_code,
        content={"status": "ready" if all_ok else "degraded", "checks": checks},
    )
