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
from postbox.keyboards.delivery import MARK_RECEIVED_PREFIX
from postbox.keyboards.journal import item_callback, journal_detail_keyboard, list_callback
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
    note: str | None = None,
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
        note=note,
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


def test_detail_shows_escaped_multiline_note() -> None:
    mail = make_mail(
        direction=MailDirection.INCOMING,
        sent_at=None,
        received_at=date(2026, 7, 15),
        note="Из синей коробки\n<бережно>",
    )

    text = journal_detail_text(mail)

    assert "Заметка:\nИз синей коробки\n&lt;бережно&gt;" in text


def test_only_travelling_outgoing_mail_has_delivery_action() -> None:
    travelling = make_mail(
        direction=MailDirection.OUTGOING,
        sent_at=date(2026, 7, 10),
        received_at=None,
    )
    delivered = make_mail(
        direction=MailDirection.OUTGOING,
        sent_at=date(2026, 7, 10),
        received_at=date(2026, 7, 15),
    )
    incoming = make_mail(
        direction=MailDirection.INCOMING,
        sent_at=None,
        received_at=date(2026, 7, 15),
    )

    travelling_keyboard = journal_detail_keyboard(travelling, MailJournalFilter.IN_TRANSIT, 2)
    delivered_keyboard = journal_detail_keyboard(delivered, MailJournalFilter.OUTGOING, 1)
    incoming_keyboard = journal_detail_keyboard(incoming, MailJournalFilter.INCOMING, 1)

    assert travelling_keyboard.inline_keyboard[0][0].callback_data == f"{MARK_RECEIVED_PREFIX}3:in_transit:2"
    assert all(
        not (button.callback_data or "").startswith(MARK_RECEIVED_PREFIX)
        for keyboard in (delivered_keyboard, incoming_keyboard)
        for row in keyboard.inline_keyboard
        for button in row
    )


def test_note_actions_follow_note_state() -> None:
    empty = make_mail(
        direction=MailDirection.INCOMING,
        sent_at=None,
        received_at=date(2026, 7, 15),
    )
    noted = make_mail(
        direction=MailDirection.INCOMING,
        sent_at=None,
        received_at=date(2026, 7, 15),
        note="В синей коробке",
    )

    empty_labels = [
        button.text
        for row in journal_detail_keyboard(empty, MailJournalFilter.ALL, 1).inline_keyboard
        for button in row
    ]
    noted_labels = [
        button.text
        for row in journal_detail_keyboard(noted, MailJournalFilter.ALL, 1).inline_keyboard
        for button in row
    ]

    assert "Добавить заметку" in empty_labels
    assert "Убрать заметку" not in empty_labels
    assert "Изменить заметку" in noted_labels
    assert "Убрать заметку" in noted_labels


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
