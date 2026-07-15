"""Allow an unknown sent date for incoming mail.

Revision ID: 20260715_0002
Revises: 20260715_0001
Create Date: 2026-07-15
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260715_0002"
down_revision: str | None = "20260715_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("mail_items", "sent_at", nullable=True)
    op.create_check_constraint(
        "ck_mail_items_direction_dates",
        "mail_items",
        "(direction = 'outgoing' AND sent_at IS NOT NULL) OR (direction = 'incoming' AND received_at IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_mail_items_direction_dates", "mail_items", type_="check")
    op.execute("UPDATE mail_items SET sent_at = received_at WHERE sent_at IS NULL")
    op.alter_column("mail_items", "sent_at", nullable=False)
