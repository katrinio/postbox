import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.types import Message
from aiogram.types import User as TelegramUser
from sqlalchemy.ext.asyncio import AsyncSession

from postbox.handlers.menu import begin_receive, begin_send, show_journal
from postbox.handlers.start import show_start
from postbox.models import User
from postbox.texts import JOURNAL_PLACEHOLDER, RECEIVE_PLACEHOLDER, SEND_PLACEHOLDER, WELCOME


@pytest.mark.parametrize(
    ("handler", "expected_text"),
    [
        (begin_send, SEND_PLACEHOLDER),
        (begin_receive, RECEIVE_PLACEHOLDER),
        (show_journal, JOURNAL_PLACEHOLDER),
    ],
)
def test_menu_handler_replies_with_placeholder(handler: object, expected_text: str) -> None:
    message = MagicMock(spec=Message)
    message.answer = AsyncMock()

    asyncio.run(handler(message))  # type: ignore[operator]

    message.answer.assert_awaited_once()
    assert message.answer.await_args.args[0] == expected_text


def test_start_replies_with_welcome() -> None:
    message = MagicMock(spec=Message)
    message.answer = AsyncMock()
    message.from_user = None
    session = AsyncMock(spec=AsyncSession)

    asyncio.run(show_start(message, session))

    message.answer.assert_awaited_once()
    assert message.answer.await_args.args[0] == WELCOME


def test_start_registers_telegram_user() -> None:
    message = MagicMock(spec=Message)
    message.answer = AsyncMock()
    message.from_user = TelegramUser(
        id=42,
        is_bot=False,
        first_name="Ada",
        username="ada",
        language_code="ru",
    )
    session = AsyncMock(spec=AsyncSession)

    with patch.object(User, "register", new=AsyncMock()) as register:
        asyncio.run(show_start(message, session))

    register.assert_awaited_once_with(
        session,
        telegram_id=42,
        username="ada",
        first_name="Ada",
        last_name=None,
        language_code="ru",
    )
