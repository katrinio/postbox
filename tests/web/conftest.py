"""Shared fixtures for web tests."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser
from typing import TYPE_CHECKING
from urllib.parse import urlencode

import httpx
import jwt
import pytest

from postbox.api import create_app
from postbox.auth import decode_jwt_token
from postbox.config import WebSettings
from postbox.models import Correspondent, MailDirection, MailItem

if TYPE_CHECKING:
    from pathlib import Path

HUB_AUTH_SECRET = "test-hub-secret-at-least-32-bytes-long"
JWT_SECRET = "test-jwt-secret-key-at-least-32-bytes-long"


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


def build_settings(tmp_path: Path, **overrides) -> WebSettings:
    """Build test WebSettings."""
    defaults = dict(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'web.db'}",
        jwt_secret_key=JWT_SECRET,
        registration_limit=5,
        hub_auth_secret=HUB_AUTH_SECRET,
        cookie_secure=False,
        dev_login=False,
        auto_create_tables=True,
    )
    defaults.update(overrides)
    return WebSettings(**defaults)


@asynccontextmanager
async def app_client(settings: WebSettings):
    """Context manager for test client with app."""
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            yield client


async def login(client: httpx.AsyncClient, *, telegram_id: int = 1, first_name: str | None = None) -> None:
    """Log in via Hub Bot auth and store the session cookie on the client."""
    auth_url = create_hub_auth_url(telegram_id)
    login_response = await client.get(auth_url)
    client.cookies.update(login_response.cookies)


# Alias for backward compatibility with test_web.py
_login = login


def get_csrf(client: httpx.AsyncClient) -> str:
    """Get CSRF token from cookies."""
    return client.cookies.get("postbox_csrf") or ""


def _current_user_id(client: httpx.AsyncClient) -> int:
    """Extract user ID from session token."""
    token = client.cookies.get("postbox_session")
    assert token is not None
    payload = decode_jwt_token(token, JWT_SECRET)
    assert payload is not None
    return int(payload["user_id"])


class _AnchorNestingParser(HTMLParser):
    """Parser to detect nested anchor tags."""

    def __init__(self) -> None:
        super().__init__()
        self._stack: list[str] = []
        self.has_nested_anchor = False

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag == "a" and "a" in self._stack:
            self.has_nested_anchor = True
        self._stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag in self._stack:
            index = len(self._stack) - 1 - self._stack[::-1].index(tag)
            del self._stack[index:]


def _has_nested_anchor(html: str) -> bool:
    """Check if HTML contains nested anchor tags."""
    parser = _AnchorNestingParser()
    parser.feed(html)
    return parser.has_nested_anchor


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


@pytest.fixture
def app_settings(tmp_path: Path) -> WebSettings:
    """Create app settings for tests."""
    return build_settings(tmp_path)


@pytest.fixture
async def web_app(app_settings: WebSettings):
    """Create and set up FastAPI app for tests."""
    app = create_app(app_settings)
    async with app.router.lifespan_context(app):
        yield app
