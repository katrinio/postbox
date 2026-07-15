"""Create users, correspondents, and mail items.

Revision ID: 20260715_0001
Revises:
Create Date: 2026-07-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260715_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

mail_direction = postgresql.ENUM("outgoing", "incoming", name="mail_direction", create_type=False)


def upgrade() -> None:
    mail_direction.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "users",
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=32), nullable=True),
        sa.Column("first_name", sa.String(length=64), nullable=False),
        sa.Column("last_name", sa.String(length=64), nullable=True),
        sa.Column("language_code", sa.String(length=16), nullable=True),
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"], unique=True)

    op.create_table(
        "correspondents",
        sa.Column("owner_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "owner_id", name="uq_correspondents_id_owner"),
        sa.UniqueConstraint("owner_id", "name", name="uq_correspondents_owner_name"),
    )
    op.create_index("ix_correspondents_owner_id", "correspondents", ["owner_id"], unique=False)

    op.create_table(
        "mail_items",
        sa.Column("owner_id", sa.BigInteger(), nullable=False),
        sa.Column("correspondent_id", sa.BigInteger(), nullable=False),
        sa.Column("direction", mail_direction, nullable=False),
        sa.Column("sent_at", sa.Date(), nullable=False),
        sa.Column("received_at", sa.Date(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "received_at IS NULL OR received_at >= sent_at",
            name="ck_mail_items_received_after_sent",
        ),
        sa.ForeignKeyConstraint(
            ["correspondent_id", "owner_id"],
            ["correspondents.id", "correspondents.owner_id"],
            name="fk_mail_items_correspondent_owner",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_mail_items_owner_direction_sent",
        "mail_items",
        ["owner_id", "direction", "sent_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_mail_items_owner_direction_sent", table_name="mail_items")
    op.drop_table("mail_items")
    op.drop_index("ix_correspondents_owner_id", table_name="correspondents")
    op.drop_table("correspondents")
    op.drop_index("ix_users_telegram_id", table_name="users")
    op.drop_table("users")
    mail_direction.drop(op.get_bind(), checkfirst=True)
