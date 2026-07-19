"""Add user approval tracking.

Revision ID: 20260719_0003
Revises: 20260715_0002
Create Date: 2026-07-19
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260719_0003"
down_revision: str | None = "20260715_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("approved_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "approved_at")
