from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, Date, Enum, ForeignKey, ForeignKeyConstraint, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from postbox.database.base import ActiveRecord

if TYPE_CHECKING:
    from postbox.models.correspondent import Correspondent
    from postbox.models.user import User


class MailDirection(StrEnum):
    OUTGOING = "outgoing"
    INCOMING = "incoming"


class MailStatus(StrEnum):
    IN_TRANSIT = "in_transit"
    RECEIVED = "received"


class MailItem(ActiveRecord):
    """A paper letter or postcard travelling between a user and a correspondent."""

    __tablename__ = "mail_items"
    __table_args__ = (
        ForeignKeyConstraint(
            ["correspondent_id", "owner_id"],
            ["correspondents.id", "correspondents.owner_id"],
            name="fk_mail_items_correspondent_owner",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "received_at IS NULL OR received_at >= sent_at",
            name="ck_mail_items_received_after_sent",
        ),
        Index("ix_mail_items_owner_direction_sent", "owner_id", "direction", "sent_at"),
    )

    owner_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    correspondent_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    direction: Mapped[MailDirection] = mapped_column(
        Enum(
            MailDirection,
            name="mail_direction",
            values_callable=lambda choices: [choice.value for choice in choices],
        ),
        nullable=False,
    )
    sent_at: Mapped[date] = mapped_column(Date, nullable=False)
    received_at: Mapped[date | None] = mapped_column(Date)
    note: Mapped[str | None] = mapped_column(Text)

    owner: Mapped[User] = relationship(
        back_populates="mail_items",
        overlaps="correspondent,mail_items",
    )
    correspondent: Mapped[Correspondent] = relationship(
        back_populates="mail_items",
        overlaps="owner,mail_items",
    )

    @property
    def status(self) -> MailStatus:
        if self.received_at is None:
            return MailStatus.IN_TRANSIT
        return MailStatus.RECEIVED
