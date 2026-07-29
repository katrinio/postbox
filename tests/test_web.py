"""Behavior tests for the server-rendered Postbox application."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta
from urllib.parse import urlencode

import httpx
import jwt

from postbox.api import create_app
from postbox.auth import decode_jwt_token
from postbox.config import WebSettings
from postbox.models import Correspondent, MailDirection, MailItem

HUB_AUTH_SECRET = "test-hub-secret-at-least-32-bytes-long"
JWT_SECRET = "test-jwt-secret-key-at-least-32-bytes-long"


def build_settings(tmp_path, **overrides) -> WebSettings:
    defaults = dict(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'web.db'}",
        jwt_secret_key=JWT_SECRET,
        registration_limit=5,
        hub_auth_secret=HUB_AUTH_SECRET,
        cookie_secure=False,
        dev_login=False,
    )
    defaults.update(overrides)
    return WebSettings(**defaults)


def create_hub_auth_url(telegram_id: int, secret: str = HUB_AUTH_SECRET) -> str:
    """Create a Hub Bot auth URL with a valid JWT token."""
    now = datetime.now(UTC)
    payload = {
        "sub": str(telegram_id),
        "aud": "postbox",
        "iss": "the-hub-bot",
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }
    token = jwt.encode(payload, secret, algorithm="HS256")
    return f"/auth/hub?{urlencode({'token': token})}"


@asynccontextmanager
async def app_client(settings: WebSettings):
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            yield client


async def _login(client: httpx.AsyncClient, *, telegram_id: int = 1, first_name: str | None = None) -> None:
    """Log in via Hub Bot auth and store the session cookie on the client."""
    auth_url = create_hub_auth_url(telegram_id)
    login = await client.get(auth_url)
    client.cookies.update(login.cookies)


def _current_user_id(client: httpx.AsyncClient) -> int:
    token = client.cookies.get("postbox_session")
    assert token is not None
    payload = decode_jwt_token(token, JWT_SECRET)
    assert payload is not None
    return int(payload["user_id"])


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
                origin_country_code=item.get("origin_country_code"),
                origin_city=item.get("origin_city"),
                destination_country_code=item.get("destination_country_code"),
                destination_city=item.get("destination_city"),
            )
        await session.commit()


# --- HTML rendering -----------------------------------------------------------


async def test_get_login_returns_html(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        response = await client.get("/login")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "The Hub" in response.text


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


async def test_authenticated_home_succeeds(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        await _login(client, telegram_id=5)
        home = await client.get("/")
    assert home.status_code == 200


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
    from datetime import UTC, datetime, timedelta

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
        first = await client.get(create_hub_auth_url(100))
        assert first.status_code == 303
        assert first.headers["location"] == "/"
        second = await client.get(create_hub_auth_url(200))
    assert second.status_code == 303
    assert second.headers["location"] == "/login?error=limit"


async def test_dev_login_disabled_returns_404(tmp_path) -> None:
    async with app_client(build_settings(tmp_path, dev_login=False)) as client:
        response = await client.post("/login", data={"telegram_id": "1", "first_name": "X", "csrf_token": "x"})
    assert response.status_code == 404


# --- Removed legacy endpoints return 404/405 ---------------------------------


async def test_legacy_api_auth_removed(tmp_path) -> None:
    """POST /api/auth/telegram was removed in Phase 5."""
    async with app_client(build_settings(tmp_path)) as client:
        response = await client.post(
            "/api/auth/telegram",
            json={"id": 1, "first_name": "X"},
        )
    assert response.status_code in (404, 405)


async def test_legacy_api_journal_removed(tmp_path) -> None:
    """GET /api/journal was removed in Phase 5."""
    async with app_client(build_settings(tmp_path)) as client:
        await _login(client)
        response = await client.get("/api/journal", headers={"Authorization": "Bearer fake"})
    assert response.status_code in (404, 405)


async def test_no_bearer_auth_path(tmp_path) -> None:
    """No endpoint accepts Bearer token auth after Phase 5."""
    async with app_client(build_settings(tmp_path)) as client:
        response = await client.get("/", headers={"Authorization": "Bearer fake-token"})
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


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
    assert "Исходящее" in response.text
    assert "Входящее" in response.text


async def test_journal_empty_state(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        await _login(client, telegram_id=20, first_name="Empty")
        response = await client.get("/")
    assert response.status_code == 200
    assert "Журнал пока пуст" in response.text
    assert "Добавить письмо" in response.text


async def test_journal_invalid_filter_defaults_to_all(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        await _login(client, telegram_id=31)
        response = await client.get("/?filter=bogus")
    assert response.status_code == 200


async def test_journal_renders_geography_compactly(tmp_path) -> None:
    today = date.today()
    settings = build_settings(tmp_path)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            await _login(client, telegram_id=32)
            user_id = _current_user_id(client)
            await _seed_mail(
                app,
                user_id,
                [
                    {
                        "correspondent": "FullRoute",
                        "direction": "outgoing",
                        "sent_at": today,
                        "origin_city": "Berlin",
                        "origin_country_code": "DE",
                        "destination_city": "Paris",
                        "destination_country_code": "FR",
                    },
                    {
                        "correspondent": "PartialRoute",
                        "direction": "incoming",
                        "received_at": today,
                        "origin_country_code": "CZ",
                        "destination_city": "Rome",
                    },
                    {"correspondent": "NoRoute", "direction": "outgoing", "sent_at": today},
                ],
            )
            response = await client.get("/")

    assert response.status_code == 200
    assert "Berlin, DE -&gt; Paris, FR" in response.text
    assert "CZ -&gt; Rome" in response.text
    assert "NoRoute" in response.text
    assert "NoRoute</h3>" in response.text


async def test_journal_escapes_city_geography(tmp_path) -> None:
    settings = build_settings(tmp_path)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            await _login(client, telegram_id=33)
            user_id = _current_user_id(client)
            await _seed_mail(
                app,
                user_id,
                [
                    {
                        "correspondent": "Escaped",
                        "direction": "outgoing",
                        "sent_at": date.today(),
                        "origin_city": '<script>alert("x")</script>',
                    }
                ],
            )
            response = await client.get("/")

    assert '<script>alert("x")</script>' not in response.text
    assert "&lt;script&gt;" in response.text


async def test_journal_geography_filters_compose_and_stay_private(tmp_path) -> None:
    today = date.today()
    settings = build_settings(tmp_path)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            await _login(client, telegram_id=34, first_name="Owner")
            owner_id = _current_user_id(client)
            await _seed_mail(
                app,
                owner_id,
                [
                    {
                        "correspondent": "BerlinOutgoing",
                        "direction": "outgoing",
                        "sent_at": today,
                        "origin_city": "Berlin",
                        "origin_country_code": "DE",
                        "destination_city": "Paris",
                        "destination_country_code": "FR",
                    },
                    {
                        "correspondent": "RomeIncoming",
                        "direction": "incoming",
                        "received_at": today,
                        "origin_city": "Rome",
                        "origin_country_code": "IT",
                        "destination_city": "Berlin",
                        "destination_country_code": "DE",
                    },
                ],
            )
            await _login(client, telegram_id=35, first_name="Other")
            other_id = _current_user_id(client)
            await _seed_mail(
                app,
                other_id,
                [
                    {
                        "correspondent": "PrivateParis",
                        "direction": "outgoing",
                        "sent_at": today,
                        "origin_city": "Berlin",
                        "origin_country_code": "DE",
                        "destination_city": "Paris",
                        "destination_country_code": "FR",
                    }
                ],
            )
            await _login(client, telegram_id=34, first_name="Owner")

            origin_country = await client.get("/?origin_country=de")
            destination_country = await client.get("/?destination_country=fr")
            origin_city = await client.get("/?origin_city= berlin ")
            destination_city = await client.get("/?destination_city=paris")
            composed = await client.get("/?filter=outgoing&origin_country=DE&destination_city=PARIS")
            invalid = await client.get("/?origin_country=bad")

    assert "BerlinOutgoing" in origin_country.text
    assert "RomeIncoming" not in origin_country.text
    assert "BerlinOutgoing" in destination_country.text
    assert "BerlinOutgoing" in origin_city.text
    assert "BerlinOutgoing" in destination_city.text
    assert "BerlinOutgoing" in composed.text
    assert "RomeIncoming" not in composed.text
    assert "PrivateParis" not in origin_country.text
    assert invalid.status_code == 200


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
        await _login(client, telegram_id=50)
        response = await client.get("/")
    assert response.status_code == 200
    assert "Postbox" in response.text
    assert "Выйти" in response.text


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


# --- Favicon, icons, PWA manifest ---------------------------------------


async def test_favicon_reachable(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        response = await client.get("/static/icons/favicon.ico")
    assert response.status_code == 200


async def test_apple_touch_icon_reachable(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        response = await client.get("/static/icons/apple-touch-icon.png")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"


async def test_icon_192_reachable(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        response = await client.get("/static/icons/icon-192.png")
    assert response.status_code == 200


async def test_icon_512_reachable(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        response = await client.get("/static/icons/icon-512.png")
    assert response.status_code == 200


async def test_icon_maskable_reachable(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        response = await client.get("/static/icons/icon-maskable-512.png")
    assert response.status_code == 200


async def test_manifest_reachable_with_correct_content_type(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        response = await client.get("/static/icons/site.webmanifest")
    assert response.status_code == 200
    assert "json" in response.headers["content-type"]
    manifest = response.json()
    assert manifest["name"] == "Postbox"
    assert manifest["display"] == "standalone"
    assert manifest["theme_color"] == "#252b2e"
    assert manifest["background_color"] == "#252b2e"


async def test_manifest_icon_urls_are_reachable(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        manifest = (await client.get("/static/icons/site.webmanifest")).json()
        for icon in manifest["icons"]:
            r = await client.get(icon["src"])
            assert r.status_code == 200, f"{icon['src']} not reachable"


async def test_html_contains_icon_and_manifest_links(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        response = await client.get("/login")
    html = response.text
    assert 'href="/static/icons/favicon.ico"' in html
    assert 'href="/static/icons/apple-touch-icon.png"' in html
    assert 'href="/static/icons/site.webmanifest"' in html
    assert 'rel="manifest"' in html


# --- Create mail --------------------------------------------------------


async def test_create_form_requires_auth(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        response = await client.get("/mail/new")
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


async def test_create_outgoing_mail(tmp_path) -> None:
    today = date.today()
    settings = build_settings(tmp_path)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            await _login(client, telegram_id=60, first_name="Creator")
            await client.get("/")
            csrf = client.cookies.get("postbox_csrf")

            response = await client.post(
                "/mail",
                data={
                    "csrf_token": csrf,
                    "direction": "outgoing",
                    "correspondent": "Маша",
                    "mail_date": str(today),
                    "note": "Открытка из Петербурга",
                },
            )
            assert response.status_code == 303
            assert response.headers["location"] == "/"

            journal = await client.get("/")
    assert "Маша" in journal.text
    assert "Открытка из Петербурга" not in journal.text  # note not in list, only on detail


async def test_create_incoming_mail(tmp_path) -> None:
    today = date.today()
    settings = build_settings(tmp_path)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            await _login(client, telegram_id=61, first_name="Receiver")
            await client.get("/")
            csrf = client.cookies.get("postbox_csrf")

            response = await client.post(
                "/mail",
                data={
                    "csrf_token": csrf,
                    "direction": "incoming",
                    "correspondent": "Аня",
                    "mail_date": str(today),
                    "note": "",
                },
            )
            assert response.status_code == 303

            journal = await client.get("/")
    assert "Аня" in journal.text
    assert "Входящее" in journal.text


async def test_create_outgoing_mail_with_full_geography(tmp_path) -> None:
    today = date.today()
    settings = build_settings(tmp_path)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            await _login(client, telegram_id=661)
            await client.get("/")
            csrf = client.cookies.get("postbox_csrf")
            response = await client.post(
                "/mail",
                data={
                    "csrf_token": csrf,
                    "direction": "outgoing",
                    "correspondent": "Geo Out",
                    "mail_date": str(today),
                    "origin_city": " Berlin ",
                    "origin_country": "de",
                    "destination_city": "Paris",
                    "destination_country": "fr",
                },
            )
            journal = await client.get("/")

    assert response.status_code == 303
    assert "Berlin, DE -&gt; Paris, FR" in journal.text


async def test_create_incoming_mail_with_full_geography(tmp_path) -> None:
    today = date.today()
    settings = build_settings(tmp_path)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            await _login(client, telegram_id=662)
            await client.get("/")
            csrf = client.cookies.get("postbox_csrf")
            response = await client.post(
                "/mail",
                data={
                    "csrf_token": csrf,
                    "direction": "incoming",
                    "correspondent": "Geo In",
                    "mail_date": str(today),
                    "origin_city": "Rome",
                    "origin_country": "it",
                    "destination_city": "Prague",
                    "destination_country": "cz",
                },
            )
            journal = await client.get("/")

    assert response.status_code == 303
    assert "Rome, IT -&gt; Prague, CZ" in journal.text


async def test_create_mail_with_partial_and_no_geography(tmp_path) -> None:
    today = date.today()
    settings = build_settings(tmp_path)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            await _login(client, telegram_id=663)
            await client.get("/")
            csrf = client.cookies.get("postbox_csrf")
            partial = await client.post(
                "/mail",
                data={
                    "csrf_token": csrf,
                    "direction": "outgoing",
                    "correspondent": "Partial",
                    "mail_date": str(today),
                    "origin_country": "de",
                    "destination_city": "Paris",
                },
            )
            none = await client.post(
                "/mail",
                data={
                    "csrf_token": csrf,
                    "direction": "outgoing",
                    "correspondent": "NoGeo",
                    "mail_date": str(today),
                },
            )
            journal = await client.get("/")

    assert partial.status_code == 303
    assert none.status_code == 303
    assert "DE -&gt; Paris" in journal.text
    assert "NoGeo" in journal.text


async def test_create_mail_rejects_invalid_country_and_preserves_geography(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        await _login(client, telegram_id=664)
        await client.get("/")
        csrf = client.cookies.get("postbox_csrf")
        response = await client.post(
            "/mail",
            data={
                "csrf_token": csrf,
                "direction": "outgoing",
                "correspondent": "Invalid Geo",
                "mail_date": str(date.today()),
                "origin_city": "Berlin",
                "origin_country": "deu",
                "destination_city": "Paris",
                "destination_country": "FR",
            },
        )

    assert response.status_code == 422
    assert "country code must be exactly 2 ASCII letters" in response.text
    assert 'value="Berlin"' in response.text
    assert 'value="deu"' in response.text


async def test_create_mail_validates_empty_correspondent(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        await _login(client, telegram_id=62)
        await client.get("/")
        csrf = client.cookies.get("postbox_csrf")
        response = await client.post(
            "/mail",
            data={"csrf_token": csrf, "direction": "outgoing", "correspondent": "  ", "mail_date": str(date.today())},
        )
    assert response.status_code == 422
    assert "Укажите имя адресата" in response.text


async def test_create_mail_validates_future_date(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        await _login(client, telegram_id=63)
        await client.get("/")
        csrf = client.cookies.get("postbox_csrf")
        response = await client.post(
            "/mail",
            data={
                "csrf_token": csrf,
                "direction": "outgoing",
                "correspondent": "Test",
                "mail_date": "2099-01-01",
            },
        )
    assert response.status_code == 422
    assert "будущем" in response.text


async def test_create_mail_requires_csrf(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        await _login(client, telegram_id=64)
        response = await client.post(
            "/mail",
            data={"csrf_token": "wrong", "direction": "outgoing", "correspondent": "X", "mail_date": str(date.today())},
        )
    assert response.status_code == 303
    assert "error=csrf" in response.headers["location"]


async def test_create_mail_preserves_values_on_error(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        await _login(client, telegram_id=65)
        await client.get("/")
        csrf = client.cookies.get("postbox_csrf")
        response = await client.post(
            "/mail",
            data={
                "csrf_token": csrf,
                "direction": "incoming",
                "correspondent": "Сергей",
                "mail_date": "",
                "note": "Тестовая заметка",
            },
        )
    assert response.status_code == 422
    assert "Сергей" in response.text
    assert "Тестовая заметка" in response.text


# --- Mail detail --------------------------------------------------------


async def test_detail_shows_item(tmp_path) -> None:
    today = date.today()
    settings = build_settings(tmp_path)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            await _login(client, telegram_id=70, first_name="Detail")
            from postbox.auth import decode_jwt_token

            token = client.cookies.get("postbox_session")
            user_id = decode_jwt_token(token, JWT_SECRET)["user_id"]
            await _seed_mail(app, user_id, [{"correspondent": "Детальная", "direction": "outgoing", "sent_at": today}])

            journal = await client.get("/")
            # Extract mail id from link
            import re

            match = re.search(r'href="/mail/(\d+)"', journal.text)
            assert match
            mail_id = match.group(1)

            response = await client.get(f"/mail/{mail_id}")
    assert response.status_code == 200
    assert "Детальная" in response.text
    assert "Исходящее письмо" in response.text
    assert "Отметить полученным" in response.text


async def test_detail_other_user_returns_404(tmp_path) -> None:
    today = date.today()
    settings = build_settings(tmp_path)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            await _login(client, telegram_id=71, first_name="Owner")
            from postbox.auth import decode_jwt_token

            token = client.cookies.get("postbox_session")
            uid = decode_jwt_token(token, JWT_SECRET)["user_id"]
            await _seed_mail(app, uid, [{"correspondent": "Secret", "direction": "outgoing", "sent_at": today}])

            await _login(client, telegram_id=72, first_name="Intruder")
            response = await client.get("/mail/1")
    assert response.status_code == 404


# --- Notes --------------------------------------------------------------


async def test_add_note(tmp_path) -> None:
    today = date.today()
    settings = build_settings(tmp_path)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            await _login(client, telegram_id=90, first_name="Noter")
            await client.get("/")
            csrf = client.cookies.get("postbox_csrf")

            await client.post(
                "/mail",
                data={
                    "csrf_token": csrf,
                    "direction": "outgoing",
                    "correspondent": "Заметочный",
                    "mail_date": str(today),
                },
            )

            journal = await client.get("/")
            import re

            match = re.search(r'href="/mail/(\d+)"', journal.text)
            assert match
            mail_id = match.group(1)

            response = await client.post(
                f"/mail/{mail_id}/note",
                data={"csrf_token": csrf, "correspondent": "Заметочный", "note": "Привет из Москвы"},
            )
            assert response.status_code == 303

            detail = await client.get(f"/mail/{mail_id}")
    assert "Привет из Москвы" in detail.text


async def test_clear_note(tmp_path) -> None:
    today = date.today()
    settings = build_settings(tmp_path)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            await _login(client, telegram_id=91, first_name="Clearer")
            await client.get("/")
            csrf = client.cookies.get("postbox_csrf")

            await client.post(
                "/mail",
                data={
                    "csrf_token": csrf,
                    "direction": "outgoing",
                    "correspondent": "Очищаемый",
                    "mail_date": str(today),
                    "note": "Будет удалено",
                },
            )

            journal = await client.get("/")
            import re

            match = re.search(r'href="/mail/(\d+)"', journal.text)
            assert match
            mail_id = match.group(1)

            response = await client.post(
                f"/mail/{mail_id}/note",
                data={"csrf_token": csrf, "correspondent": "Очищаемый", "note": ""},
            )
            assert response.status_code == 303

            detail = await client.get(f"/mail/{mail_id}")
    assert "Будет удалено" not in detail.text


async def test_change_correspondent(tmp_path) -> None:
    today = date.today()
    settings = build_settings(tmp_path)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            await _login(client, telegram_id=94, first_name="Changer")
            await client.get("/")
            csrf = client.cookies.get("postbox_csrf")

            await client.post(
                "/mail",
                data={
                    "csrf_token": csrf,
                    "direction": "outgoing",
                    "correspondent": "Старое имя",
                    "mail_date": str(today),
                },
            )

            journal = await client.get("/")
            import re

            match = re.search(r'href="/mail/(\d+)"', journal.text)
            assert match
            mail_id = match.group(1)

            response = await client.post(
                f"/mail/{mail_id}/note",
                data={"csrf_token": csrf, "correspondent": "Новое имя", "note": ""},
            )
            assert response.status_code == 303

            detail = await client.get(f"/mail/{mail_id}")
    assert "Новое имя" in detail.text
    assert "Старое имя" not in detail.text


async def test_edit_mail_geography(tmp_path) -> None:
    today = date.today()
    settings = build_settings(tmp_path)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            await _login(client, telegram_id=941, first_name="GeoEditor")
            await client.get("/")
            csrf = client.cookies.get("postbox_csrf")

            await client.post(
                "/mail",
                data={
                    "csrf_token": csrf,
                    "direction": "outgoing",
                    "correspondent": "Route",
                    "mail_date": str(today),
                },
            )
            journal = await client.get("/")
            import re

            match = re.search(r'href="/mail/(\d+)"', journal.text)
            assert match
            mail_id = match.group(1)

            response = await client.post(
                f"/mail/{mail_id}/note",
                data={
                    "csrf_token": csrf,
                    "correspondent": "Route",
                    "note": "",
                    "origin_city": "Berlin",
                    "origin_country": "de",
                    "destination_city": "Paris",
                    "destination_country": "fr",
                },
            )
            detail = await client.get(f"/mail/{mail_id}")

    assert response.status_code == 303
    assert "Berlin, DE -&gt; Paris, FR" in detail.text


async def test_note_edit_form_requires_auth(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        response = await client.get("/mail/1/edit")
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


async def test_note_other_user_returns_404(tmp_path) -> None:
    today = date.today()
    settings = build_settings(tmp_path)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            await _login(client, telegram_id=92, first_name="Owner")
            from postbox.auth import decode_jwt_token

            token = client.cookies.get("postbox_session")
            uid = decode_jwt_token(token, JWT_SECRET)["user_id"]
            await _seed_mail(app, uid, [{"correspondent": "NoteTarget", "direction": "outgoing", "sent_at": today}])

            await _login(client, telegram_id=93, first_name="Other")
            await client.get("/")
            csrf = client.cookies.get("postbox_csrf")
            response = await client.post(
                "/mail/1/note", data={"csrf_token": csrf, "correspondent": "Hacked", "note": "Hacked"}
            )
    assert response.status_code == 404


# --- HTML escaping ------------------------------------------------------


async def test_xss_in_correspondent_escaped(tmp_path) -> None:
    settings = build_settings(tmp_path)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            await _login(client, telegram_id=95, first_name="XSS")
            await client.get("/")
            csrf = client.cookies.get("postbox_csrf")

            await client.post(
                "/mail",
                data={
                    "csrf_token": csrf,
                    "direction": "outgoing",
                    "correspondent": '<script>alert("xss")</script>',
                    "mail_date": str(date.today()),
                },
            )
            journal = await client.get("/")
    assert '<script>alert("xss")</script>' not in journal.text
    assert "&lt;script&gt;" in journal.text


# --- Empty state variants -----------------------------------------------


async def test_empty_journal_has_create_cta(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        await _login(client, telegram_id=96)
        response = await client.get("/")
    assert "Журнал пока пуст" in response.text
    assert 'href="/mail/new"' in response.text


# --- Flash messages -----------------------------------------------------


async def test_create_two_mails_same_correspondent(tmp_path) -> None:
    today = date.today()
    settings = build_settings(tmp_path)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            await _login(client, telegram_id=99, first_name="Double")
            await client.get("/")
            csrf = client.cookies.get("postbox_csrf")

            await client.post(
                "/mail",
                data={"csrf_token": csrf, "direction": "outgoing", "correspondent": "Ру", "mail_date": str(today)},
            )
            response = await client.post(
                "/mail",
                data={"csrf_token": csrf, "direction": "outgoing", "correspondent": "Ру", "mail_date": str(today)},
            )
            assert response.status_code == 303

            journal = await client.get("/")
    assert journal.text.count("Ру") >= 2


async def test_flash_after_create(tmp_path) -> None:
    settings = build_settings(tmp_path)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            await _login(client, telegram_id=98, first_name="Flash")
            await client.get("/")
            csrf = client.cookies.get("postbox_csrf")

            create_resp = await client.post(
                "/mail",
                data={
                    "csrf_token": csrf,
                    "direction": "outgoing",
                    "correspondent": "Флешка",
                    "mail_date": str(date.today()),
                },
            )
            client.cookies.update(create_resp.cookies)
            journal = await client.get("/")
    assert "Письмо добавлено" in journal.text
