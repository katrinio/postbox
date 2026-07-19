from collections.abc import AsyncIterator
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from postbox.api import create_app, database_session
from postbox.config import WebSettings
from postbox.models import (
    Correspondent,
    MailDirection,
    MailItem,
    MailJournalFilter,
    MailJournalPage,
    MailJournalStats,
    User,
)

DATABASE_URL = "postgresql+psycopg://postbox:password@localhost:5432/postbox"


def make_app() -> FastAPI:
    app = create_app(WebSettings(database_url=DATABASE_URL, owner_telegram_id=42))

    async def fake_session() -> AsyncIterator[AsyncSession]:
        yield MagicMock(spec=AsyncSession)

    app.dependency_overrides[database_session] = fake_session
    return app


async def test_journal_returns_private_mail_records() -> None:
    owner = MagicMock(spec=User)
    owner.id = 7
    correspondent = Correspondent(id=2, owner_id=7, name="Мама")
    mail = MailItem(
        id=3,
        owner_id=7,
        correspondent_id=2,
        correspondent=correspondent,
        direction=MailDirection.OUTGOING,
        sent_at=date(2026, 7, 10),
        received_at=date(2026, 7, 15),
        note="Розовая открытка",
    )
    page = MailJournalPage(
        items=[mail],
        view=MailJournalFilter.ALL,
        page=1,
        pages=1,
        total=1,
    )
    stats = MailJournalStats(total=1, in_transit=0, outgoing=1, incoming=0)

    app = make_app()
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            with (
                patch.object(User, "find_by_telegram_id", new=AsyncMock(return_value=owner)) as find_owner,
                patch.object(MailItem, "journal_page", new=AsyncMock(return_value=page)) as journal_page,
                patch.object(MailItem, "journal_stats", new=AsyncMock(return_value=stats)),
            ):
                response = await client.get("/api/journal")

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "id": 3,
                "correspondent": "Мама",
                "direction": "outgoing",
                "status": "received",
                "sent_at": "2026-07-10",
                "received_at": "2026-07-15",
                "journal_date": "2026-07-10",
                "travel_days": 5,
                "note": "Розовая открытка",
            }
        ],
        "stats": {"total": 1, "in_transit": 0, "outgoing": 1, "incoming": 0},
        "page": 1,
        "pages": 1,
        "total": 1,
    }
    find_owner.assert_awaited_once()
    journal_page.assert_awaited_once()
    assert journal_page.await_args is not None
    assert journal_page.await_args.kwargs == {
        "view": MailJournalFilter.ALL,
        "page": 1,
        "page_size": 50,
    }


async def test_journal_returns_not_found_for_unknown_owner() -> None:
    app = make_app()
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            with patch.object(User, "find_by_telegram_id", new=AsyncMock(return_value=None)):
                response = await client.get("/api/journal")

    assert response.status_code == 404
    assert response.json() == {"detail": "Postbox owner is not registered yet"}


async def test_health_does_not_touch_database() -> None:
    app = make_app()
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
