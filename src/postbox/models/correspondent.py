from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from postbox.database.base import ActiveRecord

if TYPE_CHECKING:
    from postbox.models.mail_item import MailItem
    from postbox.models.user import User


class Correspondent(ActiveRecord):
    """A person in one user's private address book."""

    __tablename__ = "correspondents"
    __table_args__ = (
        UniqueConstraint("owner_id", "name", name="uq_correspondents_owner_name"),
        UniqueConstraint("id", "owner_id", name="uq_correspondents_id_owner"),
    )

    owner_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)

    owner: Mapped[User] = relationship(back_populates="correspondents")
    mail_items: Mapped[list[MailItem]] = relationship(
        back_populates="correspondent",
        overlaps="owner,mail_items",
    )
