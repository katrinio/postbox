import os
from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from postbox.models import Correspondent, MailDirection, MailItem, MailStatus, User

DATABASE_URL = os.getenv("POSTBOX_TEST_DATABASE_URL", "")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not DATABASE_URL, reason="POSTBOX_TEST_DATABASE_URL is not configured"),
]


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    engine = create_async_engine(DATABASE_URL)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        factory = async_sessionmaker(bind=connection, expire_on_commit=False)
        async with factory() as database_session:
            yield database_session
        if transaction.is_active:
            await transaction.rollback()
    await engine.dispose()


async def test_user_registration_is_idempotent(session: AsyncSession) -> None:
    first = await User.register(
        session,
        telegram_id=42,
        username="old-name",
        first_name="Ada",
        last_name=None,
        language_code="ru",
    )
    second = await User.register(
        session,
        telegram_id=42,
        username="new-name",
        first_name="Ada",
        last_name="Lovelace",
        language_code="en",
    )

    count = await session.scalar(select(func.count()).select_from(User))

    assert first.id == second.id
    assert second.username == "new-name"
    assert second.last_name == "Lovelace"
    assert count == 1


async def test_active_record_persists_mail_and_derives_status(session: AsyncSession) -> None:
    user = await User.create(
        session,
        telegram_id=100,
        username=None,
        first_name="Katrin",
        last_name=None,
        language_code="ru",
    )
    correspondent = await Correspondent.create(session, owner_id=user.id, name="Masha")
    mail = await MailItem.create(
        session,
        owner_id=user.id,
        correspondent_id=correspondent.id,
        direction=MailDirection.OUTGOING,
        sent_at=date(2026, 7, 15),
    )

    assert mail.id is not None
    assert mail.status is MailStatus.IN_TRANSIT

    mail.received_at = date(2026, 7, 20)
    await mail.save(session)

    assert mail.status is MailStatus.RECEIVED
    assert await MailItem.get(session, mail.id) is mail

    await mail.delete(session)

    assert await MailItem.get(session, mail.id) is None


async def test_mail_cannot_use_another_users_correspondent(session: AsyncSession) -> None:
    first_user = await User.create(
        session,
        telegram_id=200,
        username=None,
        first_name="First",
        last_name=None,
        language_code=None,
    )
    second_user = await User.create(
        session,
        telegram_id=201,
        username=None,
        first_name="Second",
        last_name=None,
        language_code=None,
    )
    correspondent = await Correspondent.create(session, owner_id=first_user.id, name="Private")

    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            await MailItem.create(
                session,
                owner_id=second_user.id,
                correspondent_id=correspondent.id,
                direction=MailDirection.INCOMING,
                sent_at=date(2026, 7, 15),
            )
