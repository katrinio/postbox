# ruff: noqa: RUF001

import asyncio
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram.types import Message
from aiogram.types import User as TelegramUser
from sqlalchemy.ext.asyncio import AsyncSession

from postbox.handlers.journal import (
    begin_journal,
    journal_detail_text,
    parse_item_callback,
    parse_list_callback,
)
from postbox.keyboards.journal import item_callback, list_callback
from postbox.models import (
    Correspondent,
    MailDirection,
    MailItem,
    MailJournalFilter,
    MailJournalStats,
    User,
)
from postbox.texts import JOURNAL_TITLE


def make_mail(
    *,
    direction: MailDirection,
    sent_at: date | None,
    received_at: date | None,
) -> MailItem:
    correspondent = Correspondent(id=2, owner_id=1, name="Masha <3")
    return MailItem(
        id=3,
        owner_id=1,
        correspondent_id=2,
        correspondent=correspondent,
        direction=direction,
        sent_at=sent_at,
        received_at=received_at,
    )


def test_journal_callbacks_round_trip() -> None:
    list_data = list_callback(MailJournalFilter.IN_TRANSIT, 2)
    item_data = item_callback(42, MailJournalFilter.INCOMING, 3)

    assert parse_list_callback(list_data) == (MailJournalFilter.IN_TRANSIT, 2)
    assert parse_item_callback(item_data) == (42, MailJournalFilter.INCOMING, 3)
    assert parse_list_callback("broken") is None
    assert parse_item_callback("broken") is None


def test_incoming_detail_preserves_unknown_sent_date() -> None:
    mail = make_mail(
        direction=MailDirection.INCOMING,
        sent_at=None,
        received_at=date(2026, 7, 15),
    )

    text = journal_detail_text(mail)

    assert "От кого: <b>Masha &lt;3</b>" in text
    assert "Отправлено: <b>неизвестно</b>" in text
    assert "Получено: <b>15.07.2026</b>" in text


def test_outgoing_detail_shows_current_transit_time() -> None:
    mail = make_mail(
        direction=MailDirection.OUTGOING,
        sent_at=date(2026, 7, 10),
        received_at=None,
    )

    text = journal_detail_text(mail, today=date(2026, 7, 16))

    assert "Статус: <b>в пути</b>" in text
    assert "В пути: <b>6 дн.</b>" in text


def test_begin_journal_shows_private_stats() -> None:
    message = MagicMock(spec=Message)
    message.answer = AsyncMock()
    message.from_user = TelegramUser(id=42, is_bot=False, first_name="Ada")
    session = AsyncMock(spec=AsyncSession)
    owner = MagicMock(spec=User)
    owner.id = 7
    stats = MailJournalStats(total=4, in_transit=1, outgoing=2, incoming=2)

    with (
        patch("postbox.handlers.journal.register_owner", new=AsyncMock(return_value=owner)),
        patch.object(MailItem, "journal_stats", new=AsyncMock(return_value=stats)) as journal_stats,
    ):
        asyncio.run(begin_journal(message, session))

    journal_stats.assert_awaited_once_with(session, 7)
    message.answer.assert_awaited_once()
    assert message.answer.await_args.args[0] == JOURNAL_TITLE
