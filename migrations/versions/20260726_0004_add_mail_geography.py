"""Add per-mail origin and destination geography.

Revision ID: 20260726_0004
Revises: 20260719_0003
Create Date: 2026-07-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260726_0004"
down_revision: str | None = "20260719_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("mail_items", sa.Column("origin_country_code", sa.String(length=2), nullable=True))
    op.add_column("mail_items", sa.Column("origin_city", sa.String(length=120), nullable=True))
    op.add_column("mail_items", sa.Column("destination_country_code", sa.String(length=2), nullable=True))
    op.add_column("mail_items", sa.Column("destination_city", sa.String(length=120), nullable=True))


def downgrade() -> None:
    op.drop_column("mail_items", "destination_city")
    op.drop_column("mail_items", "destination_country_code")
    op.drop_column("mail_items", "origin_city")
    op.drop_column("mail_items", "origin_country_code")
