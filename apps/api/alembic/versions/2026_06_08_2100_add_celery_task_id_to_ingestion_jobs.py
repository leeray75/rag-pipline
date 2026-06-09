"""add celery_task_id to ingestion_jobs

Revision ID: 20260608_2100
Revises: 2026_04_19_0127
Create Date: 2026-06-08 21:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260608_2100"
down_revision = "2026_04_19_0127"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add celery_task_id column to ingestion_jobs table."""
    op.add_column(
        "ingestion_jobs",
        sa.Column("celery_task_id", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    """Remove celery_task_id column from ingestion_jobs table."""
    op.drop_column("ingestion_jobs", "celery_task_id")