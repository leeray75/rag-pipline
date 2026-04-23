"""SQLAlchemy ORM models for documents."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UUID,
    Boolean,
    Float,
)
from sqlalchemy.orm import relationship

from src.database import Base


class Document(Base):
    """Represents a document that has been fetched and is being processed."""

    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("ingestion_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    url = Column(Text, nullable=False)
    title = Column(String(length=500), nullable=True)
    status = Column(String(length=20), nullable=False, default="pending")
    word_count = Column(Integer, nullable=True)
    quality_score = Column(Float, nullable=True)
    content_hash = Column(String(length=64), nullable=True)

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        server_default="now()",
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default="now()",
        onupdate="now()",
        nullable=False,
    )

    # Relationships
    job = relationship("IngestionJob", back_populates="documents")
    chunks = relationship("ChunkRecord", back_populates="document")
    review_decisions = relationship("ReviewDecision", back_populates="document")
    review_comments = relationship("ReviewComment", back_populates="document")
