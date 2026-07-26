"""Server-rendered HTML routes (Jinja2) and cookie-based authentication.

This is the new conventional web path. It coexists with the legacy JSON API
(`/api/*`) during the migration. Authentication reuses the existing JWT
(`postbox.auth`) but carries it in an HttpOnly cookie instead of a Bearer header.
"""

from __future__ import annotations

import hmac
import secrets
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, Form, HTTPException, Request, status
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import RedirectResponse, Response

from postbox.auth import create_jwt_token, decode_jwt_token, verify_telegram_login
from postbox.config import WebSettings
from postbox.models import User

PACKAGE_ROOT = Path(__file__).resolve().parent
TEMPLATES_DIR = PACKAGE_ROOT / "templates"
STATIC_DIR = PACKAGE_ROOT / "static"

SESSION_COOKIE = "postbox_session"
CSRF_COOKIE = "postbox_csrf"
# Match the JWT lifetime so the cookie and token expire together.
SESSION_MAX_AGE = 365 * 24 * 60 * 60

# Fixed, non-reflected messages keyed by an `error` code in the URL.
LOGIN_ERRORS = {
    "signature": "Не удалось проверить вход через Telegram. Попробуйте ещё раз.",
    "limit": "Регистрация временно закрыта. Достигнут лимит пользователей.",
    "unconfigured": "Вход через Telegram ещё не настроен на этом сервере.",
    "csrf": "Сессия устарела. Обновите страницу и попробуйте снова.",
}

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
router = APIRouter()


class NotAuthenticated(Exception):
    """Raised when an HTML route has no valid session cookie."""


async def web_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.database.session_factory() as session:
        yield session


def _settings(request: Request) -> WebSettings:
    return request.app.state.web_settings


async def current_user_id(request: Request) -> int:
    """Resolve the authenticated user id from the session cookie (HTML routes)."""
    settings = _settings(request)
    token = request.cookies.get(SESSION_COOKIE)
    payload = decode_jwt_token(token, settings.jwt_secret_key) if token else None
    if not payload or payload.get("user_id") is None:
        raise NotAuthenticated
    return int(payload["user_id"])


def _set_session_cookie(response: Response, token: str, settings: WebSettings) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")


def _csrf_token(request: Request) -> str:
    return request.cookies.get(CSRF_COOKIE) or secrets.token_urlsafe(32)


def _set_csrf_cookie(response: Response, token: str, settings: WebSettings) -> None:
    response.set_cookie(
        CSRF_COOKIE,
        token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
    )


def _verify_csrf(request: Request, form_token: str) -> None:
    cookie_token = request.cookies.get(CSRF_COOKIE, "")
    if not cookie_token or not hmac.compare_digest(cookie_token, form_token):
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/login?error=csrf"})


@router.get("/login")
async def login_page(request: Request) -> Response:
    settings = _settings(request)
    csrf = _csrf_token(request)
    code = request.query_params.get("error")
    response = templates.TemplateResponse(
        request,
        "login.html",
        {
            "bot_username": settings.bot_username,
            "dev_login": settings.dev_login,
            "csrf_token": csrf,
            "error": LOGIN_ERRORS.get(code) if code else None,
        },
    )
    _set_csrf_cookie(response, csrf, settings)
    return response


@router.get("/auth/telegram")
async def telegram_callback(
    request: Request,
    session: Annotated[AsyncSession, Depends(web_session)],
) -> Response:
    """Telegram Login Widget redirect callback (GET, signed query parameters)."""
    settings = _settings(request)
    data = dict(request.query_params)
    if "hash" not in data or "id" not in data or "first_name" not in data:
        return RedirectResponse("/login?error=signature", status_code=303)
    if not settings.bot_token and not settings.dev_login:
        return RedirectResponse("/login?error=unconfigured", status_code=303)
    if not verify_telegram_login(data, bot_token=settings.bot_token or "", allow_dev_hash=settings.dev_login):
        return RedirectResponse("/login?error=signature", status_code=303)
    return await _login_user(
        session,
        settings,
        telegram_id=int(data["id"]),
        first_name=data["first_name"],
        username=data.get("username") or None,
        last_name=data.get("last_name") or None,
        language_code=data.get("language_code") or None,
    )


@router.post("/login")
async def dev_login(
    request: Request,
    session: Annotated[AsyncSession, Depends(web_session)],
    telegram_id: Annotated[int, Form()],
    first_name: Annotated[str, Form()],
    csrf_token: Annotated[str, Form()],
    username: Annotated[str | None, Form()] = None,
) -> Response:
    """Development-only login form (enabled by POSTBOX_DEV_LOGIN)."""
    settings = _settings(request)
    if not settings.dev_login:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    _verify_csrf(request, csrf_token)
    return await _login_user(
        session,
        settings,
        telegram_id=telegram_id,
        first_name=first_name,
        username=username or None,
        last_name=None,
        language_code=None,
    )


async def _login_user(
    session: AsyncSession,
    settings: WebSettings,
    *,
    telegram_id: int,
    first_name: str,
    username: str | None,
    last_name: str | None,
    language_code: str | None,
) -> Response:
    user = await User.register(
        session,
        telegram_id=telegram_id,
        username=username,
        first_name=first_name,
        last_name=last_name,
        language_code=language_code,
        auto_approve=False,
    )
    if not await user.approve_within_limit(session, limit=settings.registration_limit):
        return RedirectResponse("/login?error=limit", status_code=303)
    await session.commit()
    token = create_jwt_token(user.id, user.telegram_id, settings.jwt_secret_key)
    response = RedirectResponse("/", status_code=303)
    _set_session_cookie(response, token, settings)
    return response


@router.post("/logout")
async def logout(request: Request, csrf_token: Annotated[str, Form()]) -> Response:
    _verify_csrf(request, csrf_token)
    response = RedirectResponse("/login", status_code=303)
    _clear_session_cookie(response)
    return response


@router.get("/")
async def home(
    request: Request,
    user_id: Annotated[int, Depends(current_user_id)],
    session: Annotated[AsyncSession, Depends(web_session)],
) -> Response:
    settings = _settings(request)
    user = await User.get(session, user_id)
    if user is None:
        raise NotAuthenticated
    csrf = _csrf_token(request)
    response = templates.TemplateResponse(request, "home.html", {"user": user, "csrf_token": csrf})
    _set_csrf_cookie(response, csrf, settings)
    return response


async def _redirect_to_login(request: Request, exc: Exception) -> Response:
    return RedirectResponse("/login", status_code=303)


def register_web(app: FastAPI) -> None:
    """Attach the server-rendered path: static files, HTML routes, auth handler."""
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.add_exception_handler(NotAuthenticated, _redirect_to_login)
    app.include_router(router)
