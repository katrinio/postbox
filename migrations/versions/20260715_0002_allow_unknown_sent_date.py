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
    with op.batch_alter_table("mail_items") as batch_op:
        batch_op.alter_column("sent_at", nullable=True)
        batch_op.create_check_constraint(
            "ck_mail_items_direction_dates",
            "(direction = 'outgoing' AND sent_at IS NOT NULL) OR (direction = 'incoming' AND received_at IS NOT NULL)",
        )


def downgrade() -> None:
    op.execute("UPDATE mail_items SET sent_at = received_at WHERE sent_at IS NULL")
    with op.batch_alter_table("mail_items") as batch_op:
        batch_op.drop_constraint("ck_mail_items_direction_dates", type_="check")
        batch_op.alter_column("sent_at", nullable=False)
