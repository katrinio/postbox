import asyncio
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.types import User as TelegramUser
from postbox.handlers.common import parse_date
from postbox.handlers.receive import ReceiveMail, begin_receive, confirm_receive, receive_confirmation_text
from sqlalchemy.ext.asyncio import AsyncSession

from postbox.models import Correspondent, MailDirection, MailItem, User


def test_sent_date_cannot_be_later_than_received_date() -> None:
    received_at = date(2026, 7, 15)

    assert parse_date("14.07.2026", latest=received_at) == date(2026, 7, 14)
    assert parse_date("16.07.2026", latest=received_at) is None


def test_confirmation_preserves_unknown_sent_date() -> None:
    text = receive_confirmation_text(
        "Masha <3",
        sent_at=None,
        received_at=date(2026, 7, 15),
    )

    assert "Masha &lt;3" in text
    assert "Отправлено: <b>неизвестно</b>" in text
    assert "Получено: <b>15.07.2026</b>" in text


def test_begin_receive_opens_sender_selection() -> None:
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
        asyncio.run(begin_receive(message, state, session))

    state.clear.assert_awaited_once_with()
    state.update_data.assert_awaited_once_with(owner_id=7)
    state.set_state.assert_awaited_once_with(ReceiveMail.choosing_sender)
    assert message.answer.await_count == 2


def test_confirm_receive_persists_unknown_sent_date() -> None:
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
        "sender_name": "Masha",
        "sent_at": None,
        "received_at": "2026-07-15",
    }
    session = AsyncMock(spec=AsyncSession)
    correspondent = MagicMock(spec=Correspondent)
    correspondent.id = 11
    correspondent.name = "Masha"

    with (
        patch.object(Correspondent, "find_or_create", new=AsyncMock(return_value=correspondent)),
        patch.object(MailItem, "create", new=AsyncMock()) as create_mail,
    ):
        asyncio.run(confirm_receive(callback, state, session))

    create_mail.assert_awaited_once_with(
        session,
        owner_id=7,
        correspondent_id=11,
        direction=MailDirection.INCOMING,
        sent_at=None,
        received_at=date(2026, 7, 15),
    )
    state.clear.assert_awaited_once_with()
    message.edit_text.assert_awaited_once()
    message.answer.assert_awaited_once()
