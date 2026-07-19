import asyncio
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.types import User as TelegramUser
from postbox.handlers.send import SendMail, begin_send, confirm_send, confirmation_text, parse_sent_date
from sqlalchemy.ext.asyncio import AsyncSession

from postbox.models import Correspondent, MailDirection, MailItem, User


def test_parse_sent_date_accepts_past_date() -> None:
    assert parse_sent_date("07.06.2026", today=date(2026, 7, 15)) == date(2026, 6, 7)


def test_parse_sent_date_rejects_invalid_and_future_dates() -> None:
    assert parse_sent_date("2026-06-07", today=date(2026, 7, 15)) is None
    assert parse_sent_date("16.07.2026", today=date(2026, 7, 15)) is None


def test_confirmation_escapes_recipient_name() -> None:
    text = confirmation_text("Masha <3", date(2026, 7, 15))

    assert "Masha &lt;3" in text
    assert "15.07.2026" in text


def test_begin_send_opens_recipient_selection() -> None:
    message = MagicMock(spec=Message)
    message.answer = AsyncMock()
    message.from_user = TelegramUser(id=42, is_bot=False, first_name="Ada")
    state = AsyncMock(spec=FSMContext)
    session = AsyncMock(spec=AsyncSession)
    owner = MagicMock(spec=User)
    owner.id = 7

    with (
        patch.object(User, "register", new=AsyncMock(return_value=owner)),
        patch.object(Correspondent, "for_owner", new=AsyncMock(return_value=[])),
    ):
        asyncio.run(begin_send(message, state, session))

    state.clear.assert_awaited_once_with()
    state.update_data.assert_awaited_once_with(owner_id=7)
    state.set_state.assert_awaited_once_with(SendMail.choosing_recipient)
    assert message.answer.await_count == 2


def test_confirm_send_persists_outgoing_mail() -> None:
    message = MagicMock(spec=Message)
    message.edit_text = AsyncMock()
    message.answer = AsyncMock()
    callback = MagicMock(spec=CallbackQuery)
    callback.message = message
    callback.answer = AsyncMock()
    state = AsyncMock(spec=FSMContext)
    state.get_data.return_value = {
        "owner_id": 7,
        "correspondent_id": None,
        "recipient_name": "Masha",
        "sent_at": "2026-07-15",
    }
    session = AsyncMock(spec=AsyncSession)
    correspondent = MagicMock(spec=Correspondent)
    correspondent.id = 11
    correspondent.name = "Masha"

    with (
        patch.object(Correspondent, "find_or_create", new=AsyncMock(return_value=correspondent)),
        patch.object(MailItem, "create", new=AsyncMock()) as create_mail,
    ):
        asyncio.run(confirm_send(callback, state, session))

    create_mail.assert_awaited_once_with(
        session,
        owner_id=7,
        correspondent_id=11,
        direction=MailDirection.OUTGOING,
        sent_at=date(2026, 7, 15),
    )
    state.clear.assert_awaited_once_with()
    message.edit_text.assert_awaited_once()
    message.answer.assert_awaited_once()
