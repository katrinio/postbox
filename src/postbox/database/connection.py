from sqlalchemy import event
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from postbox.config import ConfigurationError


class Database:
    """Own the async database engine and session factory for the process."""

    def __init__(self, url: str) -> None:
        parsed = make_url(url)
        if parsed.get_backend_name() == "sqlite" and parsed.get_driver_name() != "aiosqlite":
            message = (
                f"SQLite requires the async driver: use 'sqlite+aiosqlite://' instead of '{parsed.drivername}://'."
            )
            raise ConfigurationError(message)

        self.engine: AsyncEngine = create_async_engine(
            url,
            pool_pre_ping=True,
            pool_size=3,
            max_overflow=2,
        )

        # SQLite ignores foreign keys unless enabled per connection. Enable it on
        # every new DBAPI connection for SQLite engines only.
        if self.engine.dialect.name == "sqlite":

            @event.listens_for(self.engine.sync_engine, "connect")
            def _enable_sqlite_foreign_keys(dbapi_connection, connection_record) -> None:  # type: ignore[no-untyped-def]
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

        self.session_factory = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def dispose(self) -> None:
        await self.engine.dispose()
