from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Date,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Text,
    case,
    func,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column, relationship, selectinload

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


class MailDeliveryError(ValueError):
    """Raised when a mail delivery transition is not valid."""


class MailNoteError(ValueError):
    """Raised when a mail note cannot be saved."""


MAX_NOTE_LENGTH = 1000


class MailJournalFilter(StrEnum):
    ALL = "all"
    IN_TRANSIT = "in_transit"
    OUTGOING = "outgoing"
    INCOMING = "incoming"


@dataclass(frozen=True, slots=True)
class MailJournalStats:
    total: int
    in_transit: int
    outgoing: int
    incoming: int


@dataclass(frozen=True, slots=True)
class MailJournalPage:
    items: list[MailItem]
    view: MailJournalFilter
    page: int
    pages: int
    total: int


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
        CheckConstraint(
            "(direction = 'outgoing' AND sent_at IS NOT NULL) OR (direction = 'incoming' AND received_at IS NOT NULL)",
            name="ck_mail_items_direction_dates",
        ),
        Index("ix_mail_items_owner_direction_sent", "owner_id", "direction", "sent_at"),
    )

    owner_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    correspondent_id: Mapped[int] = mapped_column(Integer, nullable=False)
    direction: Mapped[MailDirection] = mapped_column(
        Enum(
            MailDirection,
            name="mail_direction",
            values_callable=lambda choices: [choice.value for choice in choices],
        ),
        nullable=False,
    )
    sent_at: Mapped[date | None] = mapped_column(Date)
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

    @property
    def journal_date(self) -> date:
        value = self.sent_at if self.direction is MailDirection.OUTGOING else self.received_at
        if value is None:
            message = f"{self.direction.value} mail {self.id} has no journal date"
            raise ValueError(message)
        return value

    def travel_days(self, *, today: date | None = None) -> int | None:
        if self.sent_at is None:
            return None
        end = self.received_at or today or date.today()
        return (end - self.sent_at).days

    async def mark_received(self, session: AsyncSession, *, received_at: date) -> MailItem:
        if self.direction is not MailDirection.OUTGOING:
            raise MailDeliveryError("only outgoing mail can be marked as received")
        if self.received_at is not None:
            raise MailDeliveryError("mail is already received")
        if self.sent_at is None or received_at < self.sent_at:
            raise MailDeliveryError("received date cannot be earlier than sent date")
        if received_at > date.today():
            raise MailDeliveryError("received date cannot be in the future")
        self.received_at = received_at
        return await self.save(session)

    @staticmethod
    def normalize_note(note: str) -> str:
        normalized = note.strip()
        if not normalized:
            raise MailNoteError("mail note cannot be empty")
        if len(normalized) > MAX_NOTE_LENGTH:
            raise MailNoteError("mail note is too long")
        return normalized

    async def set_note(self, session: AsyncSession, *, note: str | None) -> MailItem:
        self.note = None if note is None else self.normalize_note(note)
        return await self.save(session)

    @classmethod
    async def journal_stats(cls, session: AsyncSession, owner_id: int) -> MailJournalStats:
        statement = select(
            func.count(cls.id),
            func.count(cls.id).filter(cls.direction == MailDirection.OUTGOING, cls.received_at.is_(None)),
            func.count(cls.id).filter(cls.direction == MailDirection.OUTGOING),
            func.count(cls.id).filter(cls.direction == MailDirection.INCOMING),
        ).where(cls.owner_id == owner_id)
        total, in_transit, outgoing, incoming = (await session.execute(statement)).one()
        return MailJournalStats(
            total=int(total),
            in_transit=int(in_transit),
            outgoing=int(outgoing),
            incoming=int(incoming),
        )

    @classmethod
    async def journal_page(
        cls,
        session: AsyncSession,
        owner_id: int,
        *,
        view: MailJournalFilter,
        page: int = 1,
        page_size: int = 5,
    ) -> MailJournalPage:
        conditions = [cls.owner_id == owner_id]
        if view is MailJournalFilter.IN_TRANSIT:
            conditions.extend([cls.direction == MailDirection.OUTGOING, cls.received_at.is_(None)])
        elif view is MailJournalFilter.OUTGOING:
            conditions.append(cls.direction == MailDirection.OUTGOING)
        elif view is MailJournalFilter.INCOMING:
            conditions.append(cls.direction == MailDirection.INCOMING)

        total = int(await session.scalar(select(func.count(cls.id)).where(*conditions)) or 0)
        pages = max(1, (total + page_size - 1) // page_size)
        current_page = min(max(1, page), pages)
        journal_date = case(
            (cls.direction == MailDirection.OUTGOING, cls.sent_at),
            else_=cls.received_at,
        )
        statement = (
            select(cls)
            .options(selectinload(cls.correspondent))
            .where(*conditions)
            .order_by(journal_date.desc(), cls.id.desc())
            .offset((current_page - 1) * page_size)
            .limit(page_size)
        )
        items = list(await session.scalars(statement))
        return MailJournalPage(
            items=items,
            view=view,
            page=current_page,
            pages=pages,
            total=total,
        )

    @classmethod
    async def find_for_owner(
        cls,
        session: AsyncSession,
        *,
        owner_id: int,
        mail_id: int,
    ) -> MailItem | None:
        statement = (
            select(cls).options(selectinload(cls.correspondent)).where(cls.id == mail_id, cls.owner_id == owner_id)
        )
        return await session.scalar(statement)
