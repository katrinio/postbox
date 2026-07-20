from datetime import datetime
from typing import Any, Self

from sqlalchemy import DateTime, Integer, func
from sqlalchemy.ext.asyncio import AsyncAttrs, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(AsyncAttrs, DeclarativeBase):
    """Declarative root for every Postbox record."""


class ActiveRecord(Base):
    """Small asynchronous Active Record API with explicit transactions."""

    __abstract__ = True

    # A plain Integer primary key is portable: SQLite maps it to a rowid alias
    # (INTEGER PRIMARY KEY) and PostgreSQL to SERIAL, so inserts auto-populate on
    # both without supplying an id.
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    @classmethod
    async def create(cls, session: AsyncSession, **values: Any) -> Self:
        record = cls(**values)
        return await record.save(session)

    @classmethod
    async def get(cls, session: AsyncSession, record_id: int) -> Self | None:
        return await session.get(cls, record_id)

    async def save(self, session: AsyncSession) -> Self:
        session.add(self)
        await session.flush()
        await session.refresh(self)
        return self

    async def delete(self, session: AsyncSession) -> None:
        await session.delete(self)
        await session.flush()
