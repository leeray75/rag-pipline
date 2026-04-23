"""SQLAlchemy ORM models for review decisions and comments."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UUID,
    Boolean,
)
from sqlalchemy.orm import relationship

from src.database import Base


class ReviewDecision(Base):
    """Represents a review decision for a document."""

    __tablename__ = "review_decisions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("documents.id"),
        nullable=False,
    )
    job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("ingestion_jobs.id"),
        nullable=False,
    )
    decision = Column(String(length=20), nullable=False)  # "approved" | "rejected" | "edited"
    reviewer_notes = Column(Text, nullable=True)
    edited_content = Column(Text, nullable=True)

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
    document = relationship("Document", back_populates="review_decisions")
    job = relationship("IngestionJob", back_populates="review_decisions")


class ReviewComment(Base):
    """Represents a review comment on a document."""

    __tablename__ = "review_comments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("documents.id"),
        nullable=False,
    )
    line_number = Column(Integer, nullable=True)
    content = Column(Text, nullable=False)
    author = Column(String(length=100), nullable=False)
    resolved = Column(Boolean, nullable=False, default=False)

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
    document = relationship("Document", back_populates="review_comments")
