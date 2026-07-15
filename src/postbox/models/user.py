from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, String, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column, relationship

from postbox.database.base import ActiveRecord

if TYPE_CHECKING:
    from postbox.models.correspondent import Correspondent
    from postbox.models.mail_item import MailItem


class User(ActiveRecord):
    """A Telegram user who owns one private Postbox journal."""

    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(32))
    first_name: Mapped[str] = mapped_column(String(64), nullable=False)
    last_name: Mapped[str | None] = mapped_column(String(64))
    language_code: Mapped[str | None] = mapped_column(String(16))

    correspondents: Mapped[list[Correspondent]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan",
    )
    mail_items: Mapped[list[MailItem]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan",
        overlaps="correspondent,mail_items",
    )

    @classmethod
    async def find_by_telegram_id(cls, session: AsyncSession, telegram_id: int) -> User | None:
        statement = select(cls).where(cls.telegram_id == telegram_id)
        return await session.scalar(statement)

    @classmethod
    async def register(
        cls,
        session: AsyncSession,
        *,
        telegram_id: int,
        username: str | None,
        first_name: str,
        last_name: str | None,
        language_code: str | None,
    ) -> User:
        user = await cls.find_by_telegram_id(session, telegram_id)
        if user is None:
            return await cls.create(
                session,
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                language_code=language_code,
            )

        user.username = username
        user.first_name = first_name
        user.last_name = last_name
        user.language_code = language_code
        return await user.save(session)
