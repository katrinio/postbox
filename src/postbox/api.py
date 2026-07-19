from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date, datetime
from typing import Annotated, Any, Literal

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from postbox.auth import AuthErrorResponse, AuthResponse, TelegramAuthData, create_jwt_token, decode_jwt_token, validate_telegram_signature
from postbox.config import WebSettings
from postbox.database import Database
from postbox.logging import configure_logging
from postbox.models import MailDirection, MailItem, MailJournalFilter, MailStatus, User
from postbox.telegram_notifier import send_telegram_message


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


class TelegramLoginRequest(BaseModel):
    """Telegram Login Widget data."""

    id: int
    first_name: str
    username: str | None = None
    last_name: str | None = None
    language_code: str | None = None
    photo_url: str | None = None
    auth_date: int
    hash: str


async def database_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.database.session_factory() as session:
        yield session


async def get_current_user(request: Request, web_settings_arg: WebSettings | None = None) -> int:
    """Extract and validate JWT token, return user_id.

    Args:
        request: FastAPI request
        web_settings_arg: Optional settings override for testing

    Returns:
        Authenticated user_id

    Raises:
        HTTPException: If token is invalid or missing
    """
    settings = web_settings_arg or request.app.state.web_settings
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header",
        )

    token = auth_header[7:]  # Remove "Bearer " prefix
    payload = decode_jwt_token(token, settings.jwt_secret_key)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    user_id: int | None = payload.get("user_id")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    return user_id


def create_app(settings: WebSettings | None = None) -> FastAPI:
    web_settings = settings or WebSettings.from_env()
    configure_logging(web_settings.log_level)
    database = Database(web_settings.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.database = database
        app.state.owner_telegram_id = web_settings.owner_telegram_id
        app.state.web_settings = web_settings
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
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.get("/api/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse()

    @app.post("/api/auth/telegram")
    async def telegram_auth(
        request: Request,
        login_data: TelegramLoginRequest,
        session: Annotated[AsyncSession, Depends(database_session)],
    ) -> AuthResponse | AuthErrorResponse:
        """Authenticate user via Telegram Login Widget."""
        # Validate Telegram signature
        data_dict = login_data.model_dump()
        if not validate_telegram_signature(data_dict.copy(), web_settings.bot_token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Telegram signature",
            )

        # Register or get user
        user = await User.register(
            session,
            telegram_id=login_data.id,
            username=login_data.username,
            first_name=login_data.first_name,
            last_name=login_data.last_name,
            language_code=login_data.language_code,
            auto_approve=False,
        )

        # Check if user is already approved
        if user.is_approved():
            token = create_jwt_token(
                user.id,
                user.telegram_id,
                web_settings.jwt_secret_key,
            )
            return AuthResponse(
                token=token,
                user_id=user.id,
                telegram_id=user.telegram_id,
                is_approved=True,
            )

        # Owner is always approved immediately
        if login_data.id == web_settings.owner_telegram_id:
            user.approved_at = datetime.now()
            await user.save(session)
            token = create_jwt_token(
                user.id,
                user.telegram_id,
                web_settings.jwt_secret_key,
            )
            return AuthResponse(
                token=token,
                user_id=user.id,
                telegram_id=user.telegram_id,
                is_approved=True,
            )

        # Check registration limit for other users
        approved_count = await User.count_approved(session)
        if approved_count >= web_settings.registration_limit:
            # Send notification to owner
            message = (
                f"🔔 *Попытка входа: превышен лимит регистраций*\n\n"
                f"👤 {login_data.first_name}"
            )
            if login_data.username:
                message += f" (@{login_data.username})"
            message += f"\n🆔 Telegram ID: `{login_data.id}`\n\n"
            message += f"📊 Зарегистрировано: {approved_count}/{web_settings.registration_limit}"

            await send_telegram_message(
                web_settings.bot_token,
                web_settings.owner_telegram_id,
                message,
            )

            return AuthErrorResponse(
                message="Регистрация временно закрыта. Администратор был уведомлен о вашем запросе.",
                status="awaiting_approval",
            )

        # Auto-approve new user if under limit
        user.approved_at = datetime.now()
        await user.save(session)

        token = create_jwt_token(
            user.id,
            user.telegram_id,
            web_settings.jwt_secret_key,
        )
        return AuthResponse(
            token=token,
            user_id=user.id,
            telegram_id=user.telegram_id,
            is_approved=True,
        )

    @app.get("/api/journal", response_model=JournalResponse)
    async def journal(
        session: Annotated[AsyncSession, Depends(database_session)],
        user_id: Annotated[int, Depends(get_current_user)],
        page: Annotated[int, Query(ge=1)] = 1,
        page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    ) -> JournalResponse:
        journal_page = await MailItem.journal_page(
            session,
            user_id,
            view=MailJournalFilter.ALL,
            page=page,
            page_size=page_size,
        )
        stats = await MailItem.journal_stats(session, user_id)
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
