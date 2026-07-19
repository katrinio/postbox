"""Telegram authentication and JWT token management."""

from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from pydantic import BaseModel


class TelegramAuthData(BaseModel):
    """Telegram Login Widget auth data."""

    id: int
    first_name: str
    username: str | None = None
    last_name: str | None = None
    language_code: str | None = None
    photo_url: str | None = None
    auth_date: int
    hash: str


class AuthResponse(BaseModel):
    """Response for successful authentication."""

    token: str
    user_id: int
    telegram_id: int
    is_approved: bool


class AuthErrorResponse(BaseModel):
    """Response when user needs admin approval."""

    message: str
    status: str


def validate_telegram_signature(data: dict[str, Any], token: str, allow_dev_hash: bool = True) -> bool:
    """Validate Telegram Login Widget signature.

    Args:
        data: Dictionary with all parameters from Telegram (including 'hash')
        token: Bot token for signing
        allow_dev_hash: Allow dev_hash_* for development (default True)

    Returns:
        True if signature is valid, False otherwise
    """
    received_hash = data.pop("hash", None)
    if not received_hash:
        return False

    # Allow dev hashes in development
    if allow_dev_hash and received_hash.startswith("dev_hash_"):
        return True

    # Create data check string
    data_check_list = []
    for key in sorted(data.keys()):
        data_check_list.append(f"{key}={data[key]}")
    data_check_string = "\n".join(data_check_list)

    # Calculate expected hash
    secret_key = hashlib.sha256(token.encode()).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    return calculated_hash == received_hash


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
