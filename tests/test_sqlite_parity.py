"""Production-parity tests against SQLite (the documented default database).

These run without external infrastructure: a temporary file-backed SQLite
database is built through the real ``Database`` engine, so the foreign-key
PRAGMA and schema creation exercise the production code path. PostgreSQL
compatibility is covered separately by the ``integration``-marked tests in
``test_models.py``.
"""

from __future__ import annotations

from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from postbox.config import ConfigurationError
from postbox.database import Database
from postbox.database.base import Base
from postbox.models import Correspondent, MailDirection, MailItem, User


@pytest_asyncio.fixture
async def database(tmp_path):
    db = Database(f"sqlite+aiosqlite:///{tmp_path / 'parity.db'}")
    async with db.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield db
    await db.dispose()


async def _make_user(session, telegram_id: int, name: str = "User") -> User:
    return await User.create(
        session,
        telegram_id=telegram_id,
        username=None,
        first_name=name,
        last_name=None,
        language_code=None,
    )


def test_sync_sqlite_url_is_rejected() -> None:
    with pytest.raises(ConfigurationError, match="aiosqlite"):
        Database("sqlite:////data/postbox.db")


async def test_new_sqlite_connection_enables_foreign_keys(database: Database) -> None:
    async with database.engine.connect() as connection:
        enabled = (await connection.execute(text("PRAGMA foreign_keys"))).scalar()
    assert enabled == 1


async def test_inserts_generate_integer_ids_without_explicit_id(database: Database) -> None:
    async with database.session_factory() as session:
        user = await _make_user(session, telegram_id=1)
        assert isinstance(user.id, int) and user.id > 0

        correspondent = await Correspondent.create(session, owner_id=user.id, name="Masha")
        assert isinstance(correspondent.id, int) and correspondent.id > 0

        mail = await MailItem.create(
            session,
            owner_id=user.id,
            correspondent_id=correspondent.id,
            direction=MailDirection.OUTGOING,
            sent_at=date(2026, 7, 15),
        )
        assert isinstance(mail.id, int) and mail.id > 0
        await session.commit()


async def test_row_referencing_missing_user_is_rejected(database: Database) -> None:
    async with database.session_factory() as session:
        with pytest.raises(IntegrityError):
            await Correspondent.create(session, owner_id=999, name="Ghost owner")


async def test_mail_cannot_use_another_users_correspondent(database: Database) -> None:
    async with database.session_factory() as session:
        first = await _make_user(session, telegram_id=10, name="First")
        second = await _make_user(session, telegram_id=11, name="Second")
        correspondent = await Correspondent.create(session, owner_id=first.id, name="Private")
        await session.commit()
        second_id, correspondent_id = second.id, correspondent.id

    async with database.session_factory() as session:
        with pytest.raises(IntegrityError):
            await MailItem.create(
                session,
                owner_id=second_id,
                correspondent_id=correspondent_id,
                direction=MailDirection.INCOMING,
                sent_at=None,
                received_at=date(2026, 7, 20),
            )


async def test_on_delete_cascade_removes_children(database: Database) -> None:
    async with database.session_factory() as session:
        user = await _make_user(session, telegram_id=20)
        correspondent = await Correspondent.create(session, owner_id=user.id, name="X")
        await MailItem.create(
            session,
            owner_id=user.id,
            correspondent_id=correspondent.id,
            direction=MailDirection.OUTGOING,
            sent_at=date(2026, 7, 15),
        )
        await session.commit()
        user_id = user.id

    # Delete the parent row directly so the database (not the ORM cascade) is
    # what removes the children.
    async with database.session_factory() as session:
        await session.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
        await session.commit()

    async with database.session_factory() as session:
        correspondents = (await session.execute(text("SELECT count(*) FROM correspondents"))).scalar()
        mail_items = (await session.execute(text("SELECT count(*) FROM mail_items"))).scalar()
    assert correspondents == 0
    assert mail_items == 0


async def test_check_constraints_reject_invalid_dates(database: Database) -> None:
    async with database.session_factory() as session:
        user = await _make_user(session, telegram_id=30)
        correspondent = await Correspondent.create(session, owner_id=user.id, name="Y")
        await session.commit()
        user_id, correspondent_id = user.id, correspondent.id

    async with database.session_factory() as session:
        with pytest.raises(IntegrityError):
            await MailItem.create(
                session,
                owner_id=user_id,
                correspondent_id=correspondent_id,
                direction=MailDirection.OUTGOING,
                sent_at=date(2026, 7, 20),
                received_at=date(2026, 7, 1),
            )

    async with database.session_factory() as session:
        with pytest.raises(IntegrityError):
            await MailItem.create(
                session,
                owner_id=user_id,
                correspondent_id=correspondent_id,
                direction=MailDirection.OUTGOING,
                sent_at=None,
            )
