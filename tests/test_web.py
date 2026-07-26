"""Behavior tests for the server-rendered HTML path (Phases 1-3)."""

from __future__ import annotations

import hashlib
import hmac
import time
from contextlib import asynccontextmanager
from datetime import date, timedelta

import httpx

from postbox.api import create_app
from postbox.config import WebSettings
from postbox.models import Correspondent, MailDirection, MailItem

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


async def _login(client: httpx.AsyncClient, *, telegram_id: int = 1, first_name: str = "Katrin") -> None:
    """Log in and store the session cookie on the client."""
    login = await client.get("/auth/telegram", params=signed_login(id=telegram_id, first_name=first_name))
    client.cookies.update(login.cookies)


async def _seed_mail(app, owner_id: int, items: list[dict]) -> None:
    """Insert mail items via the DB session for test setup."""
    db = app.state.database
    async with db.session_factory() as session:
        for item in items:
            corr = await Correspondent.find_or_create(session, owner_id=owner_id, name=item["correspondent"])
            await MailItem.create(
                session,
                owner_id=owner_id,
                correspondent_id=corr.id,
                direction=MailDirection(item["direction"]),
                sent_at=item.get("sent_at"),
                received_at=item.get("received_at"),
                note=item.get("note"),
            )
        await session.commit()


# --- HTML rendering -----------------------------------------------------------


async def test_get_login_returns_html(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        response = await client.get("/login")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "telegram-widget.js" in response.text


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
    bad["hash"] = "0" * 64
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
        await _login(client, telegram_id=5, first_name="Katrin")
        home = await client.get("/")
    assert home.status_code == 200
    assert "Katrin" in home.text


async def test_logout_clears_cookie(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        await _login(client, telegram_id=6, first_name="Bye")
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
        await _login(client, telegram_id=7, first_name="NoCsrf")
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


# --- Phase 2: Telegram auth hardening ----------------------------------------


async def test_legacy_api_auth_rejects_invalid_signature(tmp_path) -> None:
    """POST /api/auth/telegram must reject fabricated signatures."""
    async with app_client(build_settings(tmp_path)) as client:
        response = await client.post(
            "/api/auth/telegram",
            json={
                "id": 999,
                "first_name": "Hacker",
                "auth_date": int(time.time()),
                "hash": "0" * 64,
            },
        )
    assert response.status_code == 401


async def test_legacy_api_auth_rejects_dev_hash_by_default(tmp_path) -> None:
    """POST /api/auth/telegram must not accept dev_hash_* when dev_login=False."""
    async with app_client(build_settings(tmp_path, dev_login=False)) as client:
        response = await client.post(
            "/api/auth/telegram",
            json={
                "id": 999,
                "first_name": "DevBypass",
                "auth_date": int(time.time()),
                "hash": "dev_hash_anything",
            },
        )
    assert response.status_code == 401


async def test_legacy_api_auth_accepts_valid_signature(tmp_path) -> None:
    """POST /api/auth/telegram still works with a correctly-signed payload."""
    params = signed_login(id=50, first_name="Valid")
    async with app_client(build_settings(tmp_path)) as client:
        response = await client.post(
            "/api/auth/telegram",
            json={
                "id": 50,
                "first_name": "Valid",
                "auth_date": int(params["auth_date"]),
                "hash": params["hash"],
            },
        )
    assert response.status_code == 200
    body = response.json()
    assert "token" in body
    assert body["is_approved"] is True


async def test_legacy_api_auth_rejects_stale(tmp_path) -> None:
    """POST /api/auth/telegram rejects stale auth_date."""
    stale_time = int(time.time()) - 7 * 24 * 3600
    params = signed_login(id=51, first_name="Stale", auth_date=stale_time)
    async with app_client(build_settings(tmp_path)) as client:
        response = await client.post(
            "/api/auth/telegram",
            json={
                "id": 51,
                "first_name": "Stale",
                "auth_date": stale_time,
                "hash": params["hash"],
            },
        )
    assert response.status_code == 401


async def test_both_auth_paths_enforce_crypto(tmp_path) -> None:
    """Neither /auth/telegram nor /api/auth/telegram accept empty-token dev bypass."""
    settings = build_settings(tmp_path, bot_token=BOT_TOKEN, dev_login=False)
    async with app_client(settings) as client:
        web = await client.get(
            "/auth/telegram",
            params={"id": "1", "first_name": "X", "auth_date": str(int(time.time())), "hash": "dev_hash_test"},
        )
        assert web.status_code == 303
        assert "error=signature" in web.headers["location"]

        api = await client.post(
            "/api/auth/telegram",
            json={"id": 1, "first_name": "X", "auth_date": int(time.time()), "hash": "dev_hash_test"},
        )
        assert api.status_code == 401


# --- Phase 2: Journal HTML ---------------------------------------------------


async def test_unauthenticated_journal_redirects(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        response = await client.get("/")
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


async def test_authenticated_journal_returns_html(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        await _login(client)
        response = await client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Журнал" in response.text


async def test_journal_renders_mail_items(tmp_path) -> None:
    today = date.today()
    settings = build_settings(tmp_path)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            await _login(client, telegram_id=10, first_name="Katrin")
            # Need user id — read it from the JWT
            from postbox.auth import decode_jwt_token

            token = client.cookies.get("postbox_session")
            user_id = decode_jwt_token(token, JWT_SECRET)["user_id"]

            await _seed_mail(
                app,
                user_id,
                [
                    {"correspondent": "Маша", "direction": "outgoing", "sent_at": today - timedelta(days=5)},
                    {
                        "correspondent": "Аня",
                        "direction": "incoming",
                        "received_at": today - timedelta(days=2),
                        "sent_at": today - timedelta(days=10),
                    },
                ],
            )

            response = await client.get("/")

    assert response.status_code == 200
    assert "Маша" in response.text
    assert "Аня" in response.text
    assert "Для Маша" in response.text
    assert "От Аня" in response.text


async def test_journal_empty_state(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        await _login(client, telegram_id=20, first_name="Empty")
        response = await client.get("/")
    assert response.status_code == 200
    assert "нет писем" in response.text


async def test_journal_filter_in_transit(tmp_path) -> None:
    today = date.today()
    settings = build_settings(tmp_path)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            await _login(client, telegram_id=30, first_name="Filter")
            from postbox.auth import decode_jwt_token

            token = client.cookies.get("postbox_session")
            user_id = decode_jwt_token(token, JWT_SECRET)["user_id"]

            await _seed_mail(
                app,
                user_id,
                [
                    {"correspondent": "InTransit", "direction": "outgoing", "sent_at": today - timedelta(days=3)},
                    {
                        "correspondent": "Received",
                        "direction": "outgoing",
                        "sent_at": today - timedelta(days=10),
                        "received_at": today - timedelta(days=1),
                    },
                ],
            )

            all_resp = await client.get("/")
            filtered = await client.get("/?filter=in_transit")

    assert "InTransit" in all_resp.text
    assert "Received" in all_resp.text
    assert "InTransit" in filtered.text
    assert "Received" not in filtered.text


async def test_journal_invalid_filter_defaults_to_all(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        await _login(client, telegram_id=31)
        response = await client.get("/?filter=bogus")
    assert response.status_code == 200


async def test_journal_other_user_data_not_visible(tmp_path) -> None:
    today = date.today()
    settings = build_settings(tmp_path)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            # User A creates data
            await _login(client, telegram_id=40, first_name="Alice")
            from postbox.auth import decode_jwt_token

            token_a = client.cookies.get("postbox_session")
            uid_a = decode_jwt_token(token_a, JWT_SECRET)["user_id"]
            await _seed_mail(
                app,
                uid_a,
                [
                    {"correspondent": "SecretPerson", "direction": "outgoing", "sent_at": today},
                ],
            )

            # User B logs in
            await _login(client, telegram_id=41, first_name="Bob")
            response = await client.get("/")

    assert response.status_code == 200
    assert "SecretPerson" not in response.text


async def test_journal_shows_navigation(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        await _login(client, telegram_id=50, first_name="Nav")
        response = await client.get("/")
    assert response.status_code == 200
    assert "Postbox" in response.text
    assert "Выйти" in response.text
    assert "Nav" in response.text


# --- Phase 3: routing / proxy ------------------------------------------------


async def test_all_routes_served_by_single_app(tmp_path) -> None:
    """All production routes are served by the FastAPI app (no vinext dependency)."""
    async with app_client(build_settings(tmp_path)) as client:
        login = await client.get("/login")
        assert login.status_code == 200

        static = await client.get("/static/css/app.css")
        assert static.status_code == 200

        health = await client.get("/api/health")
        assert health.status_code == 200
        assert health.json() == {"status": "ok"}

        ready = await client.get("/api/ready")
        assert ready.status_code == 200

        root = await client.get("/")
        assert root.status_code == 303
        assert root.headers["location"] == "/login"


async def test_forwarded_proto_header_respected(tmp_path) -> None:
    """When X-Forwarded-Proto is set, redirects should use the forwarded scheme."""
    async with app_client(build_settings(tmp_path)) as client:
        response = await client.get("/", headers={"x-forwarded-proto": "https"})
    assert response.status_code == 303
    location = response.headers["location"]
    assert location == "/login" or location.startswith("https://")


async def test_static_pages_css_served(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        response = await client.get("/static/css/pages.css")
    assert response.status_code == 200
    assert "site-header" in response.text
