import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession

from postbox.database.middleware import DatabaseSessionMiddleware


def make_middleware() -> tuple[DatabaseSessionMiddleware, AsyncMock]:
    session = AsyncMock(spec=AsyncSession)
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=session)
    context.__aexit__ = AsyncMock(return_value=None)
    session_factory = MagicMock(return_value=context)
    return DatabaseSessionMiddleware(session_factory), session


def test_middleware_commits_successful_update() -> None:
    middleware, session = make_middleware()
    handler = AsyncMock(return_value="done")
    event = MagicMock(spec=TelegramObject)
    data: dict[str, object] = {}

    result = asyncio.run(middleware(handler, event, data))

    assert result == "done"
    assert data["session"] is session
    session.commit.assert_awaited_once_with()
    session.rollback.assert_not_awaited()


def test_middleware_rolls_back_failed_update() -> None:
    middleware, session = make_middleware()
    handler = AsyncMock(side_effect=RuntimeError("broken update"))
    event = MagicMock(spec=TelegramObject)

    with pytest.raises(RuntimeError, match="broken update"):
        asyncio.run(middleware(handler, event, {}))

    session.rollback.assert_awaited_once_with()
    session.commit.assert_not_awaited()
