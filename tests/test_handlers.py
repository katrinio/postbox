import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import Message

from postbox.handlers.menu import begin_receive, begin_send, show_journal
from postbox.handlers.start import show_start
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

    asyncio.run(show_start(message))

    message.answer.assert_awaited_once()
    assert message.answer.await_args.args[0] == WELCOME
