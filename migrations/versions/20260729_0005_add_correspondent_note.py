"""Add note field to correspondents table.

Revision ID: 20260729_0005
Revises: 20260726_0004
Create Date: 2026-07-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260729_0005"
down_revision: str | None = "20260726_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("correspondents", sa.Column("note", sa.Text, nullable=True))


def downgrade() -> None:
    op.drop_column("correspondents", "note")
