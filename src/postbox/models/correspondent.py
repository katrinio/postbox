from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column, relationship

from postbox.database.base import ActiveRecord

if TYPE_CHECKING:
    from postbox.models.mail_item import MailItem
    from postbox.models.user import User


MAX_CORRESPONDENT_NOTE_LENGTH = 250


class CorrespondentNoteError(ValueError):
    """Raised when a correspondent note cannot be saved."""


@dataclass(frozen=True, slots=True)
class CorrespondentSummary:
    correspondent: Correspondent
    outgoing_count: int
    incoming_count: int


class Correspondent(ActiveRecord):
    """A person in one user's private address book."""

    __tablename__ = "correspondents"
    __table_args__ = (
        UniqueConstraint("owner_id", "name", name="uq_correspondents_owner_name"),
        UniqueConstraint("id", "owner_id", name="uq_correspondents_id_owner"),
    )

    owner_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    owner: Mapped[User] = relationship(back_populates="correspondents")
    mail_items: Mapped[list[MailItem]] = relationship(
        back_populates="correspondent",
        overlaps="owner,mail_items",
        passive_deletes=True,
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

    @staticmethod
    def normalize_note(note: str | None) -> str | None:
        if note is None:
            return None
        normalized = note.strip()
        if not normalized:
            return None
        if len(normalized) > MAX_CORRESPONDENT_NOTE_LENGTH:
            raise CorrespondentNoteError("Заметка слишком длинная (максимум 250 символов).")
        return normalized

    @classmethod
    async def summaries_for_owner(cls, session: AsyncSession, owner_id: int) -> list[CorrespondentSummary]:
        from postbox.models.mail_item import MailDirection, MailItem

        statement = (
            select(
                cls,
                func.count(MailItem.id).filter(MailItem.direction == MailDirection.OUTGOING),
                func.count(MailItem.id).filter(MailItem.direction == MailDirection.INCOMING),
            )
            .outerjoin(
                MailItem,
                (MailItem.owner_id == cls.owner_id) & (MailItem.correspondent_id == cls.id),
            )
            .where(cls.owner_id == owner_id)
            .group_by(cls.id)
            .order_by(func.lower(cls.name), cls.id)
        )
        rows = await session.execute(statement)
        return [
            CorrespondentSummary(
                correspondent=correspondent,
                outgoing_count=int(outgoing_count),
                incoming_count=int(incoming_count),
            )
            for correspondent, outgoing_count, incoming_count in rows
        ]

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
        statement = select(cls).where(cls.owner_id == owner_id)
        results = list(await session.scalars(statement))
        name_lower = name.casefold()
        for c in results:
            if c.name.casefold() == name_lower:
                return c
        return await cls.create(session, owner_id=owner_id, name=name)

    async def delete(self, session: AsyncSession) -> None:
        from postbox.models.mail_item import MailItem

        await session.execute(
            update(MailItem)
            .where(MailItem.owner_id == self.owner_id, MailItem.correspondent_id == self.id)
            .values(correspondent_id=None)
        )
        await super().delete(session)
