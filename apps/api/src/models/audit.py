"""SQLAlchemy ORM models for audit reports."""

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
    JSON,
)
from sqlalchemy.orm import relationship

from src.database import Base


class AuditReport(Base):
    """Represents an audit report for a job."""

    __tablename__ = "audit_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("ingestion_jobs.id"),
        nullable=False,
    )
    round = Column(Integer, nullable=False)
    total_issues = Column(Integer, nullable=False)
    issues_json = Column(JSON, nullable=True)
    summary = Column(Text, nullable=True)
    status = Column(String(length=30), nullable=False)
    agent_notes = Column(Text, nullable=True)

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
    job = relationship("IngestionJob", back_populates="audit_reports")
