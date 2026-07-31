"""Tests for Tests for infrastructure, routing, and configuration.."""

from __future__ import annotations

from .conftest import (
    _login,
    app_client,
    build_settings,
    create_hub_auth_url,
)


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


async def test_apple_touch_icon_reachable(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        response = await client.get("/static/icons/apple-touch-icon.png")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"


async def test_authenticated_home_succeeds(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        await _login(client, telegram_id=5)
        home = await client.get("/")
    assert home.status_code == 200


async def test_favicon_reachable(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        response = await client.get("/static/icons/favicon.ico")
    assert response.status_code == 200


async def test_forwarded_proto_header_respected(tmp_path) -> None:
    """When X-Forwarded-Proto is set, redirects should use the forwarded scheme."""
    async with app_client(build_settings(tmp_path)) as client:
        response = await client.get("/", headers={"x-forwarded-proto": "https"})
    assert response.status_code == 303
    location = response.headers["location"]
    assert location == "/login" or location.startswith("https://")


async def test_health_and_ready_still_json(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        health = await client.get("/api/health")
        ready = await client.get("/api/ready")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    assert ready.status_code == 200
    assert ready.json() == {"status": "ok"}


async def test_html_contains_icon_and_manifest_links(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        response = await client.get("/login")
    html = response.text
    assert 'href="/static/icons/favicon.ico"' in html
    assert 'href="/static/icons/apple-touch-icon.png"' in html
    assert 'href="/static/icons/site.webmanifest"' in html
    assert 'rel="manifest"' in html


# --- Create mail --------------------------------------------------------


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


async def test_manifest_icon_urls_are_reachable(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        manifest = (await client.get("/static/icons/site.webmanifest")).json()
        for icon in manifest["icons"]:
            r = await client.get(icon["src"])
            assert r.status_code == 200, f"{icon['src']} not reachable"


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


async def test_no_bearer_auth_path(tmp_path) -> None:
    """No endpoint accepts Bearer token auth after Phase 5."""
    async with app_client(build_settings(tmp_path)) as client:
        response = await client.get("/", headers={"Authorization": "Bearer fake-token"})
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


# --- Phase 2: Journal HTML ---------------------------------------------------


async def test_registration_limit_is_preserved(tmp_path) -> None:
    settings = build_settings(tmp_path, registration_limit=1)
    async with app_client(settings) as client:
        first = await client.get(create_hub_auth_url(100))
        assert first.status_code == 303
        assert first.headers["location"] == "/"
        second = await client.get(create_hub_auth_url(200))
    assert second.status_code == 303
    assert second.headers["location"] == "/login?error=limit"


async def test_static_css_is_served(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        response = await client.get("/static/css/app.css")
    assert response.status_code == 200
    assert "--color-canvas" in response.text


async def test_static_pages_css_served(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        response = await client.get("/static/css/pages.css")
    assert response.status_code == 200
    assert "site-header" in response.text


# --- Favicon, icons, PWA manifest ---------------------------------------
