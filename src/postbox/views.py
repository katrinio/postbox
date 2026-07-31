"""Server-rendered HTML routes (Jinja2) and cookie-based authentication."""

from __future__ import annotations

import hmac
import logging
import secrets
from collections.abc import AsyncIterator
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Annotated
from urllib.parse import quote, unquote, urlencode

import pycountry
from fastapi import APIRouter, Depends, FastAPI, Form, HTTPException, Request, status
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import RedirectResponse, Response

from postbox.auth import create_jwt_token, decode_jwt_token, verify_hub_token
from postbox.auth.hub import HubAuthError
from postbox.config import WebSettings
from postbox.models import (
    Correspondent,
    CorrespondentNoteError,
    MailDirection,
    MailGeographyError,
    MailItem,
    MailJournalFilter,
    MailNoteError,
    User,
)

logger = logging.getLogger(__name__)

PACKAGE_ROOT = Path(__file__).resolve().parent
TEMPLATES_DIR = PACKAGE_ROOT / "templates"
STATIC_DIR = PACKAGE_ROOT / "static"

SESSION_COOKIE = "postbox_session"
CSRF_COOKIE = "postbox_csrf"
FLASH_COOKIE = "postbox_flash"
SESSION_MAX_AGE = 365 * 24 * 60 * 60

LOGIN_ERRORS = {
    "signature": "Не удалось проверить вход через Telegram. Попробуйте ещё раз.",
    "limit": "Регистрация временно закрыта. Достигнут лимит пользователей.",
    "unconfigured": "Вход через Telegram ещё не настроен на этом сервере.",
    "csrf": "Сессия устарела. Обновите страницу и попробуйте снова.",
    "hub_auth": "Ссылка для входа недействительна или устарела. Вернись в The Hub и открой Postbox снова.",
}

_DATE_MONTHS = [
    "",
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
]


def _format_date(value: date) -> str:
    return f"{value.day} {_DATE_MONTHS[value.month]}"


@lru_cache(maxsize=1)
def _get_countries_list() -> tuple[dict[str, str], ...]:
    """Return a sorted list of ISO 3166-1 alpha-2 countries with names for UI."""
    return tuple(
        {"code": country.alpha_2, "name": country.name} for country in sorted(pycountry.countries, key=lambda c: c.name)
    )


def _format_status(item: MailItem) -> str:
    if item.direction is MailDirection.INCOMING:
        return "Получено"
    return "Отправлено"


def _format_location(city: str | None, country_code: str | None) -> str:
    parts = [part for part in (city, country_code) if part]
    return ", ".join(parts)


def _format_route(item: MailItem) -> str:
    origin = _format_location(item.origin_city, item.origin_country_code)
    destination = _format_location(item.destination_city, item.destination_country_code)
    if origin and destination:
        return f"{origin} -> {destination}"
    return origin or destination


def _journal_url(
    *,
    filter_value: str = "all",
    correspondent_id: int | None = None,
    page: int | None = None,
    country: str | None = None,
) -> str:
    params: dict[str, str | int] = {"filter": filter_value}
    if correspondent_id is not None:
        params["correspondent_id"] = correspondent_id
    if country:
        params["country"] = country
    if page is not None:
        params["page"] = page
    return f"/?{urlencode(params)}"


templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.globals["format_date"] = _format_date
templates.env.globals["format_status"] = _format_status
templates.env.globals["format_route"] = _format_route
templates.env.globals["journal_url"] = _journal_url
router = APIRouter()


class NotAuthenticated(Exception):
    """Raised when an HTML route has no valid session cookie."""


async def web_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.database.session_factory() as session:
        yield session


def _settings(request: Request) -> WebSettings:
    return request.app.state.web_settings


def _render(
    request: Request,
    name: str,
    context: dict | None = None,
    status_code: int = 200,
) -> Response:
    """Render a Jinja2 template with automatic static_version in context."""
    if context is None:
        context = {}
    context.setdefault("request", request)
    context.setdefault("static_version", _settings(request).static_version)
    return templates.TemplateResponse(request, name=name, context=context, status_code=status_code)


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


def _empty_mail_form_values() -> dict[str, str]:
    return {
        "direction": "outgoing",
        "correspondent": "",
        "date": str(date.today()),
        "note": "",
        "origin_city": "",
        "origin_country": "",
        "destination_city": "",
        "destination_country": "",
    }


def _geography_form_values(
    *,
    origin_city: str,
    origin_country: str,
    destination_city: str,
    destination_country: str,
) -> dict[str, str]:
    return {
        "origin_city": origin_city.strip(),
        "origin_country": origin_country.strip(),
        "destination_city": destination_city.strip(),
        "destination_country": destination_country.strip(),
    }


def _geography_values_from_item(item: MailItem) -> dict[str, str]:
    return {
        "origin_city": item.origin_city or "",
        "origin_country": item.origin_country_code or "",
        "destination_city": item.destination_city or "",
        "destination_country": item.destination_country_code or "",
    }


def _parse_country_filter(request: Request, available_countries: list[str]) -> str | None:
    try:
        country = MailItem.normalize_country_code(request.query_params.get("country"))
    except MailGeographyError:
        return None
    if country not in set(available_countries):
        return None
    return country


def _validate_geography_form(
    *,
    origin_city: str,
    origin_country: str,
    destination_city: str,
    destination_country: str,
) -> tuple[dict[str, str], dict[str, str | None]]:
    errors: dict[str, str] = {}
    values: dict[str, str | None] = {
        "origin_country_code": None,
        "origin_city": None,
        "destination_country_code": None,
        "destination_city": None,
    }
    checks = [
        ("origin_country", "origin_country_code", origin_country, MailItem.normalize_country_code),
        ("destination_country", "destination_country_code", destination_country, MailItem.normalize_country_code),
        ("origin_city", "origin_city", origin_city, MailItem.normalize_city),
        ("destination_city", "destination_city", destination_city, MailItem.normalize_city),
    ]
    for error_key, value_key, raw_value, normalizer in checks:
        try:
            values[value_key] = normalizer(raw_value)
        except MailGeographyError as error:
            errors[error_key] = str(error)
    return errors, values


# --- Flash messages (cookie-based, one-shot) ---


def _set_flash(response: Response, message: str) -> None:
    response.set_cookie(FLASH_COOKIE, quote(message), max_age=30, httponly=True, samesite="lax", path="/")


def _pop_flash(request: Request, response: Response) -> str | None:

    raw = request.cookies.get(FLASH_COOKIE)
    if raw:
        response.delete_cookie(FLASH_COOKIE, path="/")
        return unquote(raw)
    return None


# --- Auth routes ---


@router.get("/login")
async def login_page(request: Request) -> Response:
    settings = _settings(request)
    if not settings.hub_bot_url:
        logger.warning("Hub Bot login link is disabled; missing config: %s", WebSettings.HUB_BOT_URL_VARIABLE)
    csrf = _csrf_token(request)
    code = request.query_params.get("error")
    response = _render(
        request,
        "login.html",
        {
            "dev_login": settings.dev_login,
            "csrf_token": csrf,
            "error": LOGIN_ERRORS.get(code) if code else None,
            "hub_bot_url": settings.hub_bot_url,
        },
    )
    _set_csrf_cookie(response, csrf, settings)
    return response


@router.get("/auth/hub")
async def hub_auth_callback(
    request: Request,
    session: Annotated[AsyncSession, Depends(web_session)],
    token: str = "",
) -> Response:
    """The Hub Bot authentication handoff (GET, signed JWT in query).

    The Hub Bot issues a short-lived JWT that authorizes the user's Telegram identity.
    This endpoint verifies the JWT and creates a Postbox session.
    """
    settings = _settings(request)
    if not settings.hub_auth_secret:
        logger.warning("Hub auth attempted but HUB_AUTH_SECRET is not configured")
        return RedirectResponse("/login?error=hub_auth", status_code=303)

    if not token or not token.strip():
        logger.debug("Hub auth: token is missing or empty")
        return RedirectResponse("/login?error=hub_auth", status_code=303)

    try:
        identity = verify_hub_token(token, settings.hub_auth_secret)
    except HubAuthError as e:
        logger.warning("Hub auth verification failed: %s", type(e).__name__)
        return RedirectResponse("/login?error=hub_auth", status_code=303)

    # Find or create Postbox user from Hub identity.
    # Hub only provides telegram_user_id (already verified by Telegram).
    user = await User.find_by_telegram_id(session, identity.telegram_user_id)
    if user is None:
        # New user: create with minimal defaults
        user = await User.create(
            session,
            telegram_id=identity.telegram_user_id,
            username=None,
            first_name="Telegram User",
            last_name=None,
            language_code=None,
            approved_at=None,
        )
        logger.info("Hub auth: created new user for telegram_id=%d", identity.telegram_user_id)
    else:
        # Existing user: do not overwrite metadata; just use as-is
        logger.debug("Hub auth: existing user telegram_id=%d", identity.telegram_user_id)

    # Apply registration limit policy (same as Telegram auth)
    if not await user.approve_within_limit(session, limit=settings.registration_limit):
        logger.info("Hub auth: registration limit reached for telegram_id=%d", identity.telegram_user_id)
        await session.commit()  # Persist the user for manual approval later
        return RedirectResponse("/login?error=limit", status_code=303)

    await session.commit()
    token_jwt = create_jwt_token(user.id, user.telegram_id, settings.jwt_secret_key)
    response = RedirectResponse("/", status_code=303)
    # Set Referrer-Policy to prevent token leakage in Referer header
    response.headers["Referrer-Policy"] = "no-referrer"
    _set_session_cookie(response, token_jwt, settings)
    return response


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


# --- Journal ---

JOURNAL_FILTERS = [
    ("all", "Все"),
    ("outgoing", "Отправленные"),
    ("incoming", "Полученные"),
]

JOURNAL_PAGE_SIZE = 50


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

    filter_param = request.query_params.get("filter", "all")
    try:
        view = MailJournalFilter(filter_param)
    except ValueError:
        view = MailJournalFilter.ALL

    page_param = request.query_params.get("page", "1")
    try:
        page = max(1, int(page_param))
    except ValueError, TypeError:
        page = 1

    correspondents = await Correspondent.for_owner(session, user_id)
    available_correspondent_ids = {correspondent.id for correspondent in correspondents}

    correspondent_id_param = request.query_params.get("correspondent_id")
    correspondent_id: int | None = None
    if correspondent_id_param:
        try:
            correspondent_id = int(correspondent_id_param)
        except ValueError, TypeError:
            correspondent_id = None
    if correspondent_id not in available_correspondent_ids:
        correspondent_id = None

    countries = await MailItem.country_codes_for_owner(session, user_id)
    country = _parse_country_filter(request, countries)

    journal = await MailItem.journal_page(
        session,
        user_id,
        view=view,
        correspondent_id=correspondent_id,
        country_code=country,
        page=page,
        page_size=JOURNAL_PAGE_SIZE,
    )
    stats = await MailItem.journal_stats(session, user_id)
    csrf = _csrf_token(request)
    raw_flash = request.cookies.get(FLASH_COOKIE)
    flash = unquote(raw_flash) if raw_flash else None
    response = _render(
        request,
        "journal.html",
        {
            "user": user,
            "journal": journal,
            "stats": stats,
            "filters": JOURNAL_FILTERS,
            "current_filter": view.value,
            "correspondents": correspondents,
            "correspondent_id": correspondent_id,
            "countries": countries,
            "country": country,
            "csrf_token": csrf,
            "flash": flash,
            "today": date.today(),
        },
    )
    if raw_flash:
        response.delete_cookie(FLASH_COOKIE, path="/")
    _set_csrf_cookie(response, csrf, settings)
    return response


# --- Create mail ---


@router.get("/mail/new")
async def new_mail_form(
    request: Request,
    user_id: Annotated[int, Depends(current_user_id)],
    session: Annotated[AsyncSession, Depends(web_session)],
) -> Response:
    settings = _settings(request)
    user = await User.get(session, user_id)
    if user is None:
        raise NotAuthenticated
    correspondents = await Correspondent.for_owner(session, user_id)
    csrf = _csrf_token(request)
    response = _render(
        request,
        "mail_form.html",
        {
            "user": user,
            "csrf_token": csrf,
            "correspondents": correspondents,
            "countries_list": list(_get_countries_list()),
            "errors": {},
            "values": _empty_mail_form_values(),
            "today": str(date.today()),
        },
    )
    _set_csrf_cookie(response, csrf, settings)
    return response


@router.post("/mail")
async def create_mail(
    request: Request,
    user_id: Annotated[int, Depends(current_user_id)],
    session: Annotated[AsyncSession, Depends(web_session)],
    csrf_token: Annotated[str, Form()],
    direction: Annotated[str, Form()] = "",
    correspondent: Annotated[str, Form()] = "",
    mail_date: Annotated[str, Form()] = "",
    note: Annotated[str, Form()] = "",
    origin_city: Annotated[str, Form()] = "",
    origin_country: Annotated[str, Form()] = "",
    destination_city: Annotated[str, Form()] = "",
    destination_country: Annotated[str, Form()] = "",
) -> Response:
    _verify_csrf(request, csrf_token)
    settings = _settings(request)
    user = await User.get(session, user_id)
    if user is None:
        raise NotAuthenticated

    errors: dict[str, str] = {}
    correspondent_name = correspondent.strip()
    if not correspondent_name:
        errors["correspondent"] = "Укажите имя адресата."
    if len(correspondent_name) > 160:
        errors["correspondent"] = "Имя слишком длинное (максимум 160 символов)."

    if direction not in ("outgoing", "incoming"):
        errors["direction"] = "Выберите направление."

    parsed_date: date | None = None
    if not mail_date.strip():
        errors["date"] = "Укажите дату."
    else:
        try:
            parsed_date = date.fromisoformat(mail_date.strip())
        except ValueError:
            errors["date"] = "Неверный формат даты."
        else:
            if parsed_date > date.today():
                errors["date"] = "Дата не может быть в будущем."

    note_text = note.strip() or None
    if note_text:
        try:
            note_text = MailItem.normalize_note(note_text)
        except MailNoteError as e:
            errors["note"] = str(e)
    geography_errors, geography_values = _validate_geography_form(
        origin_city=origin_city,
        origin_country=origin_country,
        destination_city=destination_city,
        destination_country=destination_country,
    )
    errors.update(geography_errors)

    if errors:
        correspondents = await Correspondent.for_owner(session, user_id)
        csrf = _csrf_token(request)
        response = _render(
            request,
            "mail_form.html",
            {
                "user": user,
                "csrf_token": csrf,
                "correspondents": correspondents,
                "countries_list": list(_get_countries_list()),
                "errors": errors,
                "values": {
                    "direction": direction,
                    "correspondent": correspondent_name,
                    "date": mail_date.strip(),
                    "note": note.strip(),
                    **_geography_form_values(
                        origin_city=origin_city,
                        origin_country=origin_country,
                        destination_city=destination_city,
                        destination_country=destination_country,
                    ),
                },
                "today": str(date.today()),
            },
            status_code=422,
        )
        _set_csrf_cookie(response, csrf, settings)
        return response

    corr = await Correspondent.find_or_create(session, owner_id=user_id, name=correspondent_name)

    mail_direction = MailDirection(direction)
    sent_at = parsed_date if mail_direction is MailDirection.OUTGOING else None
    received_at = parsed_date if mail_direction is MailDirection.INCOMING else None

    await MailItem.create(
        session,
        owner_id=user_id,
        correspondent_id=corr.id,
        direction=mail_direction,
        sent_at=sent_at,
        received_at=received_at,
        note=note_text,
        **geography_values,
    )
    await session.commit()

    redirect = RedirectResponse("/", status_code=303)
    _set_flash(redirect, "Письмо добавлено.")
    return redirect


# --- Mail item detail / edit ---


async def _load_item(session: AsyncSession, user_id: int, mail_id: int) -> MailItem:
    item = await MailItem.find_for_owner(session, owner_id=user_id, mail_id=mail_id)
    if item is None:
        raise HTTPException(status_code=404)
    return item


@router.get("/mail/{mail_id}")
async def mail_detail(
    request: Request,
    mail_id: int,
    user_id: Annotated[int, Depends(current_user_id)],
    session: Annotated[AsyncSession, Depends(web_session)],
) -> Response:
    settings = _settings(request)
    user = await User.get(session, user_id)
    if user is None:
        raise NotAuthenticated
    item = await _load_item(session, user_id, mail_id)
    csrf = _csrf_token(request)
    response = _render(
        request,
        "mail_detail.html",
        {
            "user": user,
            "item": item,
            "csrf_token": csrf,
            "today": date.today(),
        },
    )
    _set_csrf_cookie(response, csrf, settings)
    return response


@router.get("/mail/{mail_id}/edit")
async def edit_note_form(
    request: Request,
    mail_id: int,
    user_id: Annotated[int, Depends(current_user_id)],
    session: Annotated[AsyncSession, Depends(web_session)],
) -> Response:
    settings = _settings(request)
    user = await User.get(session, user_id)
    if user is None:
        raise NotAuthenticated
    item = await _load_item(session, user_id, mail_id)
    csrf = _csrf_token(request)
    correspondents = await Correspondent.for_owner(session, user_id)
    response = _render(
        request,
        "mail_edit.html",
        {
            "user": user,
            "item": item,
            "csrf_token": csrf,
            "errors": {},
            "correspondent_value": item.correspondent.name,
            "note_value": item.note or "",
            "geography_values": _geography_values_from_item(item),
            "correspondents": correspondents,
            "countries_list": list(_get_countries_list()),
        },
    )
    _set_csrf_cookie(response, csrf, settings)
    return response


@router.post("/mail/{mail_id}/note")
async def update_note(
    request: Request,
    mail_id: int,
    user_id: Annotated[int, Depends(current_user_id)],
    session: Annotated[AsyncSession, Depends(web_session)],
    csrf_token: Annotated[str, Form()],
    correspondent: Annotated[str, Form()] = "",
    note: Annotated[str, Form()] = "",
    origin_city: Annotated[str, Form()] = "",
    origin_country: Annotated[str, Form()] = "",
    destination_city: Annotated[str, Form()] = "",
    destination_country: Annotated[str, Form()] = "",
) -> Response:
    _verify_csrf(request, csrf_token)
    settings = _settings(request)
    user = await User.get(session, user_id)
    if user is None:
        raise NotAuthenticated
    item = await _load_item(session, user_id, mail_id)

    errors: dict[str, str] = {}
    correspondent_name = correspondent.strip()
    if not correspondent_name:
        errors["correspondent"] = "Укажите имя адресата."
    elif len(correspondent_name) > 160:
        errors["correspondent"] = "Имя слишком длинное (максимум 160 символов)."

    note_text = note.strip() or None
    if note_text:
        try:
            note_text = MailItem.normalize_note(note_text)
        except MailNoteError as e:
            errors["note"] = str(e)
    geography_errors, geography_values = _validate_geography_form(
        origin_city=origin_city,
        origin_country=origin_country,
        destination_city=destination_city,
        destination_country=destination_country,
    )
    errors.update(geography_errors)

    if errors:
        correspondents = await Correspondent.for_owner(session, user_id)
        csrf = _csrf_token(request)
        response = _render(
            request,
            "mail_edit.html",
            {
                "user": user,
                "item": item,
                "csrf_token": csrf,
                "errors": errors,
                "correspondent_value": correspondent_name,
                "note_value": note.strip(),
                "geography_values": _geography_form_values(
                    origin_city=origin_city,
                    origin_country=origin_country,
                    destination_city=destination_city,
                    destination_country=destination_country,
                ),
                "correspondents": correspondents,
                "countries_list": list(_get_countries_list()),
            },
            status_code=422,
        )
        _set_csrf_cookie(response, csrf, settings)
        return response

    if correspondent_name != item.correspondent.name:
        corr = await Correspondent.find_or_create(session, owner_id=user_id, name=correspondent_name)
        item.correspondent_id = corr.id

    await item.set_note(session, note=note_text)
    await item.set_geography(session, **geography_values)
    await session.commit()

    redirect = RedirectResponse(f"/mail/{mail_id}", status_code=303)
    _set_flash(redirect, "Изменения сохранены.")
    return redirect


# --- Correspondent detail ---


@router.get("/correspondents")
async def correspondents_index(
    request: Request,
    user_id: Annotated[int, Depends(current_user_id)],
    session: Annotated[AsyncSession, Depends(web_session)],
) -> Response:
    settings = _settings(request)
    user = await User.get(session, user_id)
    if user is None:
        raise NotAuthenticated

    summaries = await Correspondent.summaries_for_owner(session, user_id)
    csrf = _csrf_token(request)
    response = _render(
        request,
        "correspondents.html",
        {
            "user": user,
            "summaries": summaries,
            "csrf_token": csrf,
        },
    )
    _set_csrf_cookie(response, csrf, settings)
    return response


async def _load_correspondent(session: AsyncSession, user_id: int, correspondent_id: int) -> Correspondent:
    corr = await Correspondent.find_for_owner(session, owner_id=user_id, correspondent_id=correspondent_id)
    if corr is None:
        raise HTTPException(status_code=404)
    return corr


@router.get("/correspondent/{correspondent_id}")
async def correspondent_detail(
    request: Request,
    correspondent_id: int,
    user_id: Annotated[int, Depends(current_user_id)],
    session: Annotated[AsyncSession, Depends(web_session)],
) -> Response:
    settings = _settings(request)
    user = await User.get(session, user_id)
    if user is None:
        raise NotAuthenticated

    correspondent = await _load_correspondent(session, user_id, correspondent_id)

    outgoing_count, incoming_count = await MailItem.correspondent_stats(session, user_id, correspondent_id)

    journal = await MailItem.journal_page(
        session,
        user_id,
        view=MailJournalFilter.ALL,
        correspondent_id=correspondent_id,
        page_size=50,
    )

    csrf = _csrf_token(request)
    raw_flash = request.cookies.get(FLASH_COOKIE)
    flash = unquote(raw_flash) if raw_flash else None
    response = _render(
        request,
        "correspondent_detail.html",
        {
            "user": user,
            "correspondent": correspondent,
            "outgoing_count": outgoing_count,
            "incoming_count": incoming_count,
            "journal": journal,
            "csrf_token": csrf,
            "flash": flash,
            "note_error": None,
            "note_value": correspondent.note or "",
            "edit_note": False,
            "today": date.today(),
        },
    )
    if raw_flash:
        response.delete_cookie(FLASH_COOKIE, path="/")
    _set_csrf_cookie(response, csrf, settings)
    return response


@router.post("/correspondent/{correspondent_id}/note")
async def correspondent_save_note(
    request: Request,
    correspondent_id: int,
    user_id: Annotated[int, Depends(current_user_id)],
    session: Annotated[AsyncSession, Depends(web_session)],
    csrf_token: Annotated[str, Form()] = "",
    note: Annotated[str, Form()] = "",
) -> Response:
    _verify_csrf(request, csrf_token)
    user = await User.get(session, user_id)
    if user is None:
        raise NotAuthenticated

    correspondent = await _load_correspondent(session, user_id, correspondent_id)

    try:
        note_text = Correspondent.normalize_note(note)
    except CorrespondentNoteError as error:
        settings = _settings(request)
        outgoing_count, incoming_count = await MailItem.correspondent_stats(session, user_id, correspondent_id)
        journal = await MailItem.journal_page(
            session,
            user_id,
            view=MailJournalFilter.ALL,
            correspondent_id=correspondent_id,
            page_size=50,
        )
        csrf = _csrf_token(request)
        response = _render(
            request,
            "correspondent_detail.html",
            {
                "user": user,
                "correspondent": correspondent,
                "outgoing_count": outgoing_count,
                "incoming_count": incoming_count,
                "journal": journal,
                "csrf_token": csrf,
                "flash": None,
                "note_error": str(error),
                "note_value": note.strip(),
                "edit_note": True,
                "today": date.today(),
            },
            status_code=422,
        )
        _set_csrf_cookie(response, csrf, settings)
        return response

    correspondent.note = note_text
    await correspondent.save(session)
    await session.commit()

    redirect = RedirectResponse(f"/correspondent/{correspondent_id}", status_code=303)
    _set_flash(redirect, "Заметка обновлена.")
    return redirect


# --- Plumbing ---


async def _redirect_to_login(request: Request, exc: Exception) -> Response:
    return RedirectResponse("/login", status_code=303)


def register_web(app: FastAPI) -> None:
    """Attach the server-rendered path: static files, HTML routes, auth handler."""
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.add_exception_handler(NotAuthenticated, _redirect_to_login)
    app.include_router(router)
