from __future__ import annotations

from datetime import datetime
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
    approved_at: Mapped[datetime | None] = mapped_column(nullable=True)

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
    async def count_approved(cls, session: AsyncSession) -> int:
        from sqlalchemy import func

        statement = select(func.count(cls.id)).where(cls.approved_at.isnot(None))
        return int(await session.scalar(statement) or 0)

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
        auto_approve: bool = False,
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
                approved_at=datetime.now() if auto_approve else None,
            )

        user.username = username
        user.first_name = first_name
        user.last_name = last_name
        user.language_code = language_code
        if auto_approve and user.approved_at is None:
            user.approved_at = datetime.now()
        return await user.save(session)

    def is_approved(self) -> bool:
        return self.approved_at is not None

    async def approve_within_limit(self, session: AsyncSession, *, limit: int) -> bool:
        """Approve this user if the registration limit still allows it.

        Already-approved users stay approved. Otherwise the user is approved
        only while the number of approved users is below ``limit``. Returns
        whether the user is approved; ``False`` means the limit was reached and
        the user must wait for manual approval.
        """
        if self.is_approved():
            return True
        if await self.count_approved(session) >= limit:
            return False
        self.approved_at = datetime.now()
        await self.save(session)
        return True
