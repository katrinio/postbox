"""JWT token and session management."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt


def create_jwt_token(
    user_id: int,
    telegram_id: int,
    secret_key: str,
    expires_in_days: int = 365,
) -> str:
    """Create JWT token for authenticated user.

    Args:
        user_id: Internal user ID from database
        telegram_id: Telegram user ID
        secret_key: Secret key for signing
        expires_in_days: Token expiration in days

    Returns:
        Encoded JWT token
    """
    now = datetime.now(UTC)
    payload = {
        "user_id": user_id,
        "telegram_id": telegram_id,
        "iat": now,
        "exp": now + timedelta(days=expires_in_days),
    }
    return jwt.encode(payload, secret_key, algorithm="HS256")


def decode_jwt_token(token: str, secret_key: str) -> dict[str, Any] | None:
    """Decode and validate JWT token.

    Args:
        token: JWT token to decode
        secret_key: Secret key for verification

    Returns:
        Decoded payload if valid, None otherwise
    """
    try:
        return jwt.decode(token, secret_key, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        return None
