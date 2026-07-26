import os
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import create_engine, pool
from sqlalchemy.engine import make_url

from postbox.database.base import Base
from postbox.models import Correspondent, MailItem, User  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

load_dotenv(override=False)
database_url = os.getenv("POSTBOX_DATABASE_URL", "").strip()
if not database_url:
    msg = "POSTBOX_DATABASE_URL is required to run migrations"
    raise RuntimeError(msg)


def _sync_database_url(url: str) -> str:
    parsed = make_url(url)
    if parsed.drivername == "sqlite+aiosqlite":
        return parsed.set(drivername="sqlite").render_as_string(hide_password=False)
    return url


target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=_sync_database_url(database_url),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_sync_database_url(database_url), poolclass=pool.NullPool)

    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()

    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
