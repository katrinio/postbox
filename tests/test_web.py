"""Behavior tests for the server-rendered HTML path (Phase 1)."""

from __future__ import annotations

import hashlib
import hmac
import time
from contextlib import asynccontextmanager

import httpx

from postbox.api import create_app
from postbox.config import WebSettings

BOT_TOKEN = "test-bot-token:AAA"
JWT_SECRET = "test-jwt-secret-key-at-least-32-bytes-long"


def build_settings(tmp_path, **overrides) -> WebSettings:
    defaults = dict(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'web.db'}",
        jwt_secret_key=JWT_SECRET,
        registration_limit=5,
        bot_token=BOT_TOKEN,
        bot_username="postbox_bot",
        cookie_secure=False,
        dev_login=False,
    )
    defaults.update(overrides)
    return WebSettings(**defaults)


def signed_login(bot_token: str = BOT_TOKEN, *, auth_date: int | None = None, **fields) -> dict[str, str]:
    """Build a Telegram Login Widget payload with a valid HMAC signature."""
    payload = {k: str(v) for k, v in fields.items()}
    payload["auth_date"] = str(auth_date if auth_date is not None else int(time.time()))
    check = "\n".join(f"{k}={payload[k]}" for k in sorted(payload))
    secret = hashlib.sha256(bot_token.encode()).digest()
    payload["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return payload


@asynccontextmanager
async def app_client(settings: WebSettings):
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            yield client


# --- HTML rendering -----------------------------------------------------------


async def test_get_login_returns_html(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        response = await client.get("/login")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "telegram-widget.js" in response.text  # widget rendered when bot configured


async def test_static_css_is_served(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        response = await client.get("/static/css/app.css")
    assert response.status_code == 200
    assert "--color-canvas" in response.text


async def test_unauthenticated_home_redirects_to_login(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        response = await client.get("/")
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


# --- Authentication -----------------------------------------------------------


async def test_valid_telegram_login_sets_httponly_cookie_and_redirects(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        response = await client.get("/auth/telegram", params=signed_login(id=1, first_name="Ada"))
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    cookie = response.headers["set-cookie"]
    assert cookie.startswith("postbox_session=")
    assert "HttpOnly" in cookie
    assert "samesite=lax" in cookie.lower()


async def test_production_cookie_is_secure(tmp_path) -> None:
    async with app_client(build_settings(tmp_path, cookie_secure=True)) as client:
        response = await client.get("/auth/telegram", params=signed_login(id=2, first_name="Grace"))
    cookie = response.headers["set-cookie"]
    assert "Secure" in cookie
    assert "samesite=lax" in cookie.lower()
    assert "HttpOnly" in cookie


async def test_invalid_signature_is_rejected(tmp_path) -> None:
    bad = signed_login(id=3, first_name="Mallory")
    bad["hash"] = "0" * 64  # tamper
    async with app_client(build_settings(tmp_path)) as client:
        response = await client.get("/auth/telegram", params=bad)
    assert response.status_code == 303
    assert response.headers["location"] == "/login?error=signature"
    assert "set-cookie" not in response.headers


async def test_stale_auth_date_is_rejected(tmp_path) -> None:
    stale = signed_login(id=4, first_name="Old", auth_date=int(time.time()) - 7 * 24 * 3600)
    async with app_client(build_settings(tmp_path)) as client:
        response = await client.get("/auth/telegram", params=stale)
    assert response.status_code == 303
    assert response.headers["location"] == "/login?error=signature"


async def test_authenticated_home_succeeds(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        login = await client.get("/auth/telegram", params=signed_login(id=5, first_name="Katrin"))
        client.cookies.update(login.cookies)
        home = await client.get("/")
    assert home.status_code == 200
    assert "Katrin" in home.text


async def test_logout_clears_cookie(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        login = await client.get("/auth/telegram", params=signed_login(id=6, first_name="Bye"))
        client.cookies.update(login.cookies)
        await client.get("/")  # sets the CSRF cookie
        csrf = client.cookies.get("postbox_csrf")
        response = await client.post("/logout", data={"csrf_token": csrf})
    assert response.status_code == 303
    assert response.headers["location"] == "/login"
    set_cookie = response.headers["set-cookie"]
    assert set_cookie.startswith("postbox_session=")
    assert 'postbox_session="";' in set_cookie or "Max-Age=0" in set_cookie or "expires=" in set_cookie.lower()


async def test_logout_without_csrf_is_rejected(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        login = await client.get("/auth/telegram", params=signed_login(id=7, first_name="NoCsrf"))
        client.cookies.update(login.cookies)
        await client.get("/")
        response = await client.post("/logout", data={"csrf_token": "wrong-token"})
    assert response.status_code == 303
    assert response.headers["location"] == "/login?error=csrf"


# --- Existing behavior preserved ----------------------------------------------


async def test_health_and_ready_still_json(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        health = await client.get("/api/health")
        ready = await client.get("/api/ready")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    assert ready.status_code == 200
    assert ready.json() == {"status": "ok"}


async def test_registration_limit_is_preserved(tmp_path) -> None:
    settings = build_settings(tmp_path, registration_limit=1)
    async with app_client(settings) as client:
        first = await client.get("/auth/telegram", params=signed_login(id=100, first_name="First"))
        assert first.status_code == 303
        assert first.headers["location"] == "/"
        second = await client.get("/auth/telegram", params=signed_login(id=200, first_name="Second"))
    assert second.status_code == 303
    assert second.headers["location"] == "/login?error=limit"


async def test_dev_login_disabled_returns_404(tmp_path) -> None:
    async with app_client(build_settings(tmp_path, dev_login=False)) as client:
        response = await client.post("/login", data={"telegram_id": "1", "first_name": "X", "csrf_token": "x"})
    assert response.status_code == 404
