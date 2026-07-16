from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date
from typing import Annotated, Literal

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from postbox.config import WebSettings
from postbox.database import Database
from postbox.logging import configure_logging
from postbox.models import MailDirection, MailItem, MailJournalFilter, MailStatus, User


class JournalStatsResponse(BaseModel):
    total: int
    in_transit: int
    outgoing: int
    incoming: int


class JournalItemResponse(BaseModel):
    id: int
    correspondent: str
    direction: MailDirection
    status: MailStatus
    sent_at: date | None
    received_at: date | None
    journal_date: date
    travel_days: int | None
    note: str | None


class JournalResponse(BaseModel):
    items: list[JournalItemResponse]
    stats: JournalStatsResponse
    page: int
    pages: int
    total: int


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


async def database_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.database.session_factory() as session:
        yield session


def create_app(settings: WebSettings | None = None) -> FastAPI:
    web_settings = settings or WebSettings.from_env()
    configure_logging(web_settings.log_level)
    database = Database(web_settings.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.database = database
        app.state.owner_telegram_id = web_settings.owner_telegram_id
        yield
        await database.dispose()

    app = FastAPI(
        title="Postbox API",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://localhost:3001",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:3001",
        ],
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    @app.get("/api/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse()

    @app.get("/api/journal", response_model=JournalResponse)
    async def journal(
        request: Request,
        session: Annotated[AsyncSession, Depends(database_session)],
        page: Annotated[int, Query(ge=1)] = 1,
        page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    ) -> JournalResponse:
        owner = await User.find_by_telegram_id(session, request.app.state.owner_telegram_id)
        if owner is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Postbox owner is not registered yet",
            )

        journal_page = await MailItem.journal_page(
            session,
            owner.id,
            view=MailJournalFilter.ALL,
            page=page,
            page_size=page_size,
        )
        stats = await MailItem.journal_stats(session, owner.id)
        return JournalResponse(
            items=[
                JournalItemResponse(
                    id=item.id,
                    correspondent=item.correspondent.name,
                    direction=item.direction,
                    status=item.status,
                    sent_at=item.sent_at,
                    received_at=item.received_at,
                    journal_date=item.journal_date,
                    travel_days=item.travel_days(),
                    note=item.note,
                )
                for item in journal_page.items
            ],
            stats=JournalStatsResponse(
                total=stats.total,
                in_transit=stats.in_transit,
                outgoing=stats.outgoing,
                incoming=stats.incoming,
            ),
            page=journal_page.page,
            pages=journal_page.pages,
            total=journal_page.total,
        )

    return app


def run() -> None:
    uvicorn.run("postbox.api:create_app", factory=True, host="127.0.0.1", port=8000, reload=True)
