"""Async SQLAlchemy database engine and session factory."""

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from src.config import settings


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_size=20,
    max_overflow=10,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:  # type: ignore[misc]
    """FastAPI dependency that yields a database session."""
    async with async_session_factory() as session:
        yield session


# ---------------------------------------------------------------------------
# Synchronous engine for use in Celery workers (prefork/gevent/eventlet)
# ---------------------------------------------------------------------------

def _make_sync_url(async_url: str) -> str:
    """Convert an asyncpg URL to a sync psycopg2 URL."""
    return async_url.replace("+asyncpg", "+psycopg2")


_sync_engine = create_engine(
    _make_sync_url(settings.database_url),
    echo=False,
    pool_size=10,
    max_overflow=5,
)

sync_engine = _sync_engine

SyncSession = sessionmaker(sync_engine, expire_on_commit=False)
