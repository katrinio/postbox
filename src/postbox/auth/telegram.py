"""Telegram Login Widget verification."""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime


class TelegramAuthError(ValueError):
    """Telegram Login Widget payload is invalid."""


@dataclass(frozen=True)
class TelegramIdentity:
    """Verified Telegram Login Widget identity."""

    telegram_id: int
    first_name: str
    username: str | None
    last_name: str | None


EXPECTED_FIELDS = {"id", "first_name", "last_name", "username", "photo_url", "auth_date", "hash"}
REQUIRED_FIELDS = {"id", "first_name", "auth_date", "hash"}
MAX_AUTH_AGE_SECONDS = 24 * 60 * 60


def verify_telegram_login(
    items: Iterable[tuple[str, str]],
    bot_token: str,
    *,
    max_age_seconds: int = MAX_AUTH_AGE_SECONDS,
) -> TelegramIdentity:
    """Verify Telegram Login Widget query parameters."""
    if not bot_token or not bot_token.strip():
        raise TelegramAuthError("Bot token is not configured")

    values: dict[str, str] = {}
    for key, value in items:
        if key not in EXPECTED_FIELDS:
            raise TelegramAuthError("Unexpected Telegram login field")
        if key in values:
            raise TelegramAuthError("Duplicate Telegram login field")
        values[key] = value

    missing = REQUIRED_FIELDS - values.keys()
    if missing:
        raise TelegramAuthError("Missing required Telegram login field")

    try:
        telegram_id = int(values["id"])
    except ValueError as error:
        raise TelegramAuthError("Telegram user id is invalid") from error
    if telegram_id <= 0:
        raise TelegramAuthError("Telegram user id is invalid")

    first_name = values["first_name"].strip()
    if not first_name:
        raise TelegramAuthError("Telegram first name is missing")

    try:
        auth_date = int(values["auth_date"])
    except ValueError as error:
        raise TelegramAuthError("Telegram auth date is invalid") from error
    now = int(datetime.now(UTC).timestamp())
    if auth_date <= 0 or now - auth_date > max_age_seconds or auth_date - now > 60:
        raise TelegramAuthError("Telegram auth date is stale")

    provided_hash = values["hash"]
    if not provided_hash:
        raise TelegramAuthError("Telegram hash is missing")

    data_check_string = "\n".join(f"{key}={values[key]}" for key in sorted(values) if key != "hash")
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    expected_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_hash, provided_hash):
        raise TelegramAuthError("Telegram signature is invalid")

    return TelegramIdentity(
        telegram_id=telegram_id,
        first_name=first_name,
        username=values.get("username") or None,
        last_name=values.get("last_name") or None,
    )
