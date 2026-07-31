"""Tests for Tests for HTTP caching and response headers.."""

from __future__ import annotations

from postbox.config import WebSettings

from .conftest import (
    JWT_SECRET,
    app_client,
    build_settings,
)


async def test_html_responses_have_no_cache_headers(tmp_path) -> None:
    """HTML responses must have Cache-Control: no-cache, must-revalidate."""
    settings = build_settings(tmp_path)
    async with app_client(settings) as client:
        response = await client.get("/login")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-cache, must-revalidate"
        assert response.headers.get("pragma") == "no-cache"
        assert response.headers.get("expires") == "0"


async def test_static_files_without_version_have_no_cache_policy(tmp_path) -> None:
    """Static files without version query param have no explicit Cache-Control."""
    settings = build_settings(tmp_path)
    async with app_client(settings) as client:
        response = await client.get("/static/css/app.css")
        assert response.status_code == 200
        # No Cache-Control header means browser applies heuristic cache
        # ETag is present for revalidation
        assert "cache-control" not in response.headers
        assert "etag" in response.headers


async def test_static_files_with_version_have_long_cache(tmp_path) -> None:
    """Static files with version query param have aggressive cache policy."""
    settings = build_settings(tmp_path, static_version="abc123")
    async with app_client(settings) as client:
        response = await client.get("/static/css/app.css?v=abc123")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "public, max-age=31536000, immutable"


async def test_base_template_includes_static_version(tmp_path) -> None:
    """base.html must include static_version in CSS URLs."""
    settings = build_settings(tmp_path, static_version="def456")
    async with app_client(settings) as client:
        response = await client.get("/login")
        assert response.status_code == 200
        html = response.text
        assert "/static/css/app.css?v=def456" in html
        assert "/static/css/pages.css?v=def456" in html


async def test_static_version_defaults_when_not_set(tmp_path) -> None:
    """static_version should default to git SHA when not explicitly set."""
    import os

    # Reset environment so from_env() generates default
    os.environ.pop("POSTBOX_STATIC_VERSION", None)
    os.environ["POSTBOX_DATABASE_URL"] = f"sqlite+aiosqlite:///{tmp_path / 'web.db'}"
    os.environ["POSTBOX_JWT_SECRET_KEY"] = JWT_SECRET
    settings = WebSettings.from_env()
    # If not set, should be auto-generated from git
    assert len(settings.static_version) > 0


async def test_redirect_responses_dont_get_html_cache_policy(tmp_path) -> None:
    """Redirect responses (3xx) should not get HTML cache headers."""
    settings = build_settings(tmp_path, dev_login=False)
    async with app_client(settings) as client:
        response = await client.get("/", follow_redirects=False)
        assert response.status_code == 303
        # Redirects don't have content-type, so no cache headers should be set
        # (middleware only sets cache-control if content-type starts with text/html)
        assert response.headers.get("cache-control") != "no-cache, must-revalidate"


# --- Country autocomplete tests ---
