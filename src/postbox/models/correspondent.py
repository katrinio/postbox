from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, String, UniqueConstraint, func, select
from sqlalchemy.ext.asyncio import AsyncSession
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

    @classmethod
    async def for_owner(
        cls,
        session: AsyncSession,
        owner_id: int,
        *,
        limit: int = 20,
    ) -> list[Correspondent]:
        statement = select(cls).where(cls.owner_id == owner_id).order_by(cls.name).limit(limit)
        return list(await session.scalars(statement))

    @classmethod
    async def find_for_owner(
        cls,
        session: AsyncSession,
        *,
        owner_id: int,
        correspondent_id: int,
    ) -> Correspondent | None:
        statement = select(cls).where(cls.id == correspondent_id, cls.owner_id == owner_id)
        return await session.scalar(statement)

    @classmethod
    async def find_or_create(cls, session: AsyncSession, *, owner_id: int, name: str) -> Correspondent:
        statement = select(cls).where(cls.owner_id == owner_id, func.lower(cls.name) == name.lower())
        correspondent = await session.scalar(statement)
        if correspondent is not None:
            return correspondent
        return await cls.create(session, owner_id=owner_id, name=name)
