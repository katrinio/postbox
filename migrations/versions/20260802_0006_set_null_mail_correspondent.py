"""Set mail correspondent to null when deleting contacts.

Revision ID: 20260802_0006
Revises: 20260729_0005
Create Date: 2026-08-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260802_0006"
down_revision: str | None = "20260729_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("mail_items") as batch_op:
        batch_op.drop_constraint("fk_mail_items_correspondent_owner", type_="foreignkey")
        batch_op.alter_column("correspondent_id", existing_type=sa.Integer(), nullable=True)
        batch_op.create_foreign_key(
            "fk_mail_items_correspondent",
            "correspondents",
            ["correspondent_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    op.execute("DELETE FROM mail_items WHERE correspondent_id IS NULL")
    with op.batch_alter_table("mail_items") as batch_op:
        batch_op.drop_constraint("fk_mail_items_correspondent", type_="foreignkey")
        batch_op.alter_column("correspondent_id", existing_type=sa.Integer(), nullable=False)
        batch_op.create_foreign_key(
            "fk_mail_items_correspondent_owner",
            "correspondents",
            ["correspondent_id", "owner_id"],
            ["id", "owner_id"],
            ondelete="CASCADE",
        )
