"""Tests for Tests for authentication and session management.."""

from __future__ import annotations

from datetime import timedelta

from .conftest import (
    _login,
    app_client,
    build_settings,
)


async def test_get_login_returns_html(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        response = await client.get("/login")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Вход через The Hub Bot пока не настроен" in response.text


async def test_login_shows_hub_bot_link_when_configured(tmp_path) -> None:
    settings = build_settings(tmp_path, hub_bot_url="https://t.me/hub_test_bot?start=postbox")
    async with app_client(settings) as client:
        response = await client.get("/login")
    assert response.status_code == 200
    assert "telegram-widget.js" not in response.text
    assert 'href="https://t.me/hub_test_bot?start=postbox"' in response.text
    assert "Открыть The Hub" in response.text


async def test_login_handles_missing_hub_bot_link(tmp_path) -> None:
    settings = build_settings(tmp_path, hub_bot_url=None)
    async with app_client(settings) as client:
        response = await client.get("/login")
    assert response.status_code == 200
    assert "telegram-widget.js" not in response.text
    assert "Вход через The Hub Bot пока не настроен" in response.text


async def test_direct_telegram_auth_route_is_not_available(tmp_path) -> None:
    settings = build_settings(tmp_path)
    async with app_client(settings) as client:
        response = await client.get("/auth/telegram")
    assert response.status_code == 404


async def test_unauthenticated_home_redirects_to_login(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        response = await client.get("/")
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


# --- Authentication -----------------------------------------------------------


async def test_logout_clears_cookie(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        await _login(client, telegram_id=6)
        await client.get("/")
        csrf = client.cookies.get("postbox_csrf")
        response = await client.post("/logout", data={"csrf_token": csrf})
    assert response.status_code == 303
    assert response.headers["location"] == "/login"
    set_cookie = response.headers["set-cookie"]
    assert set_cookie.startswith("postbox_session=")
    assert 'postbox_session="";' in set_cookie or "Max-Age=0" in set_cookie or "expires=" in set_cookie.lower()


async def test_logout_without_csrf_is_rejected(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        await _login(client, telegram_id=7)
        await client.get("/")
        response = await client.post("/logout", data={"csrf_token": "wrong-token"})
    assert response.status_code == 303
    assert response.headers["location"] == "/login?error=csrf"


# --- Existing behavior preserved ----------------------------------------------


# --- JWT security ------------------------------------------------------------


async def test_jwt_with_wrong_algorithm_rejected(tmp_path) -> None:
    import jwt

    settings = build_settings(tmp_path)
    bad_token = jwt.encode({"user_id": 1}, settings.jwt_secret_key, algorithm="HS512")
    async with app_client(settings) as client:
        client.cookies.set("postbox_session", bad_token)
        response = await client.get("/")
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


async def test_jwt_tampered_signature_rejected(tmp_path) -> None:
    import jwt

    settings = build_settings(tmp_path)
    good_token = jwt.encode({"user_id": 1}, settings.jwt_secret_key, algorithm="HS256")
    tampered = good_token[:-10] + "0123456789"
    async with app_client(settings) as client:
        client.cookies.set("postbox_session", tampered)
        response = await client.get("/")
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


async def test_jwt_expired_rejected(tmp_path) -> None:
    from datetime import UTC, datetime

    import jwt

    settings = build_settings(tmp_path)
    expired = jwt.encode(
        {"user_id": 1, "exp": datetime.now(UTC) - timedelta(hours=1)},
        settings.jwt_secret_key,
        algorithm="HS256",
    )
    async with app_client(settings) as client:
        client.cookies.set("postbox_session", expired)
        response = await client.get("/")
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


# --- Existing behavior preserved -------------------------------------------


async def test_dev_login_disabled_returns_404(tmp_path) -> None:
    async with app_client(build_settings(tmp_path, dev_login=False)) as client:
        response = await client.post("/login", data={"telegram_id": "1", "first_name": "X", "csrf_token": "x"})
    assert response.status_code == 404


# --- Removed legacy endpoints return 404/405 ---------------------------------
