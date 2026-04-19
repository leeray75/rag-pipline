"""Routers package."""

from src.routers.auth import router as auth_router
from src.routers.health import router as health_router
from src.routers.ingest import router as ingest_router
from src.routers.jobs import router as jobs_router
from src.routers.review import router as review_router
from src.routers.websocket import router as websocket_router

__all__ = [
    "auth_router",
    "health_router",
    "ingest_router",
    "jobs_router",
    "review_router",
    "websocket_router",
]
