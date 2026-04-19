"""add content_hash to documents

Revision ID: 20260419_0127
Revises: 
Create Date: 2026-04-19 01:27:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260419_0127"
down_revision = "edaa014c2adf"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add content_hash column to documents table
    op.add_column("documents", sa.Column("content_hash", sa.String(length=64), nullable=True))


def downgrade() -> None:
    # Drop content_hash column from documents table
    op.drop_column("documents", "content_hash")
