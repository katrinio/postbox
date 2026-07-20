import os
from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from postbox.models import Correspondent, MailDirection, MailItem, MailJournalFilter, MailStatus, User

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

    count = await session.scalar(select(func.count()).select_from(User).where(User.telegram_id == 42))

    assert first.id == second.id
    assert second.username == "new-name"
    assert second.last_name == "Lovelace"
    assert count == 1


async def test_approve_within_limit_applies_registration_policy(session: AsyncSession) -> None:
    async def new_user(telegram_id: int) -> User:
        return await User.register(
            session,
            telegram_id=telegram_id,
            username=None,
            first_name="User",
            last_name=None,
            language_code=None,
        )

    first = await new_user(1001)
    second = await new_user(1002)
    third = await new_user(1003)

    # Under the limit: users are approved on demand.
    assert await first.approve_within_limit(session, limit=2) is True
    assert first.is_approved()
    assert await second.approve_within_limit(session, limit=2) is True

    # Limit reached: further users must wait, and stay unapproved.
    assert await third.approve_within_limit(session, limit=2) is False
    assert not third.is_approved()

    # Already-approved users stay approved regardless of the limit.
    assert await first.approve_within_limit(session, limit=2) is True


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

    await mail.mark_received(session, received_at=date(2026, 7, 16))

    assert mail.status is MailStatus.RECEIVED
    assert await MailItem.get(session, mail.id) is mail

    await mail.set_note(session, note="  First postcard  ")

    assert mail.note == "First postcard"

    await mail.set_note(session, note=None)

    assert mail.note is None

    await mail.delete(session)

    assert await MailItem.get(session, mail.id) is None


async def test_incoming_mail_allows_unknown_sent_date(session: AsyncSession) -> None:
    user = await User.create(
        session,
        telegram_id=125,
        username=None,
        first_name="Katrin",
        last_name=None,
        language_code="ru",
    )
    correspondent = await Correspondent.create(session, owner_id=user.id, name="Unexpected sender")

    mail = await MailItem.create(
        session,
        owner_id=user.id,
        correspondent_id=correspondent.id,
        direction=MailDirection.INCOMING,
        sent_at=None,
        received_at=date(2026, 7, 15),
    )

    assert mail.sent_at is None
    assert mail.received_at == date(2026, 7, 15)
    assert mail.status is MailStatus.RECEIVED


async def test_direction_requires_its_known_date(session: AsyncSession) -> None:
    user = await User.create(
        session,
        telegram_id=126,
        username=None,
        first_name="Katrin",
        last_name=None,
        language_code="ru",
    )
    correspondent = await Correspondent.create(session, owner_id=user.id, name="Dates")

    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            await MailItem.create(
                session,
                owner_id=user.id,
                correspondent_id=correspondent.id,
                direction=MailDirection.OUTGOING,
                sent_at=None,
            )

    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            await MailItem.create(
                session,
                owner_id=user.id,
                correspondent_id=correspondent.id,
                direction=MailDirection.INCOMING,
                sent_at=None,
                received_at=None,
            )


async def test_correspondents_are_reused_and_scoped_to_owner(session: AsyncSession) -> None:
    user = await User.create(
        session,
        telegram_id=150,
        username=None,
        first_name="Katrin",
        last_name=None,
        language_code="ru",
    )

    first = await Correspondent.find_or_create(session, owner_id=user.id, name="Masha")
    second = await Correspondent.find_or_create(session, owner_id=user.id, name="masha")
    correspondents = await Correspondent.for_owner(session, user.id)

    assert first.id == second.id
    assert correspondents == [first]
    assert (
        await Correspondent.find_for_owner(
            session,
            owner_id=user.id,
            correspondent_id=first.id,
        )
        is first
    )


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
                received_at=date(2026, 7, 20),
            )


async def test_journal_queries_are_ordered_filtered_and_private(session: AsyncSession) -> None:
    owner = await User.create(
        session,
        telegram_id=-300,
        username=None,
        first_name="Journal owner",
        last_name=None,
        language_code="ru",
    )
    another_owner = await User.create(
        session,
        telegram_id=-301,
        username=None,
        first_name="Another owner",
        last_name=None,
        language_code="ru",
    )
    person = await Correspondent.create(session, owner_id=owner.id, name="Masha")
    another_person = await Correspondent.create(session, owner_id=another_owner.id, name="Private")

    delivered = await MailItem.create(
        session,
        owner_id=owner.id,
        correspondent_id=person.id,
        direction=MailDirection.OUTGOING,
        sent_at=date(2026, 7, 1),
        received_at=date(2026, 7, 5),
    )
    travelling = await MailItem.create(
        session,
        owner_id=owner.id,
        correspondent_id=person.id,
        direction=MailDirection.OUTGOING,
        sent_at=date(2026, 7, 10),
    )
    incoming = await MailItem.create(
        session,
        owner_id=owner.id,
        correspondent_id=person.id,
        direction=MailDirection.INCOMING,
        sent_at=None,
        received_at=date(2026, 7, 15),
    )
    private = await MailItem.create(
        session,
        owner_id=another_owner.id,
        correspondent_id=another_person.id,
        direction=MailDirection.INCOMING,
        sent_at=None,
        received_at=date(2026, 7, 16),
    )

    stats = await MailItem.journal_stats(session, owner.id)
    first_page = await MailItem.journal_page(
        session,
        owner.id,
        view=MailJournalFilter.ALL,
        page=1,
        page_size=2,
    )
    second_page = await MailItem.journal_page(
        session,
        owner.id,
        view=MailJournalFilter.ALL,
        page=2,
        page_size=2,
    )
    in_transit = await MailItem.journal_page(
        session,
        owner.id,
        view=MailJournalFilter.IN_TRANSIT,
    )

    assert stats.total == 3
    assert stats.outgoing == 2
    assert stats.incoming == 1
    assert stats.in_transit == 1
    assert first_page.items == [incoming, travelling]
    assert first_page.pages == 2
    assert second_page.items == [delivered]
    assert in_transit.items == [travelling]
    assert await MailItem.find_for_owner(session, owner_id=owner.id, mail_id=private.id) is None
