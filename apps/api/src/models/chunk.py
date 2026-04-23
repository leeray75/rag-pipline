"""SQLAlchemy ORM models for chunks and vector collections."""

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UUID,
    JSON,
    Boolean,
    Float,
)
from sqlalchemy.orm import relationship

from src.database import Base


class JobStatus(str, Enum):
    """Enum for job status values."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ChunkRecord(Base):
    """Represents a chunk of text extracted from a document.

    Chunks are the basic unit of text that will be embedded and stored
    in Qdrant for semantic search.
    """

    __tablename__ = "chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("ingestion_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index = Column(Integer, nullable=False)
    total_chunks = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    token_count = Column(Integer, nullable=False)
    heading_path = Column(String(length=500), nullable=False)
    metadata_json = Column(JSON, nullable=False)

    # Embedding status: pending, embedding, embedded, failed
    embedding_status = Column(String(length=20), nullable=False, default="pending")

    # Relationships
    document = relationship("Document", back_populates="chunks")
    job = relationship("IngestionJob", back_populates="chunks")

    __table_args__ = (
        Index("ix_chunks_job_index", "job_id", "chunk_index"),
    )


class VectorCollection(Base):
    """Represents a Qdrant vector collection and its associated metadata.

    Each collection corresponds to a single Qdrant collection and tracks
    the embedding progress and statistics.
    """

    __tablename__ = "vector_collections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(length=255), nullable=False, unique=True)
    description = Column(Text, nullable=True)

    # Job association (nullable because collections can exist without a specific job)
    job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("ingestion_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Embedding configuration
    embedding_model = Column(String(length=100), nullable=False, default="BAAI/bge-small-en-v1.5")
    vector_dimensions = Column(Integer, nullable=False, default=384)

    # Statistics
    vector_count = Column(Integer, nullable=False, default=0)
    document_count = Column(Integer, nullable=False, default=0)

    # Status: creating, embedding, complete, failed
    status = Column(String(length=20), nullable=False, default="creating")
    error_message = Column(Text, nullable=True)

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
    job = relationship("IngestionJob", back_populates="vector_collections")


class IngestionJob(Base):
    """Represents an ingestion job that processes a URL."""

    __tablename__ = "ingestion_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    url = Column(Text, nullable=False)
    crawl_all_docs = Column(Boolean, nullable=False, default=False)
    status = Column(String(length=20), nullable=False, default="pending")
    total_documents = Column(Integer, nullable=True)
    processed_documents = Column(Integer, nullable=True, default=0)
    current_audit_round = Column(Integer, nullable=True, default=0)

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
    documents = relationship("Document", back_populates="job")
    chunks = relationship("ChunkRecord", back_populates="job")
    vector_collections = relationship("VectorCollection", back_populates="job")
    review_decisions = relationship("ReviewDecision", back_populates="job")
    audit_reports = relationship("AuditReport", back_populates="job")
