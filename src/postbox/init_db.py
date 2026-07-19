"""Initialize database with all tables."""

import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from postbox.database.base import Base
from postbox.models import User, MailItem, Correspondent
from postbox.config import WebSettings


async def init_db(database_url: str | None = None):
    """Create all tables."""
    if database_url is None:
        settings = WebSettings.from_env()
        database_url = settings.database_url

    engine = create_async_engine(database_url, echo=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    print("✅ Database tables created successfully!")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(init_db())
