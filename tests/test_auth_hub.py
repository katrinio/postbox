"""Tests for Hub Bot JWT verification."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
import pytest

from postbox.auth.hub import (
    HubIdentity,
    InvalidClaim,
    InvalidSignature,
    MissingClaim,
    TokenExpired,
    WrongAudience,
    WrongIssuer,
    verify_hub_token,
)


@pytest.fixture
def hub_secret() -> str:
    """Shared secret for Hub Bot JWT signing."""
    return "test-hub-auth-secret-32-chars-minimum"


@pytest.fixture
def valid_hub_token(hub_secret: str) -> str:
    """Generate a valid Hub JWT token."""
    now = datetime.now(UTC)
    payload = {
        "sub": "123456789",
        "aud": "postbox",
        "iss": "the-hub-bot",
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }
    return jwt.encode(payload, hub_secret, algorithm="HS256")


class TestHubTokenVerification:
    """Tests for verify_hub_token() function."""

    def test_valid_token_accepted(self, hub_secret: str, valid_hub_token: str) -> None:
        """Valid Hub token should be accepted and identity extracted."""
        identity = verify_hub_token(valid_hub_token, hub_secret)
        assert isinstance(identity, HubIdentity)
        assert identity.telegram_user_id == 123456789
        assert identity.profile_claims == frozenset()

    def test_valid_token_extracts_profile_claims(self, hub_secret: str) -> None:
        """Valid Hub token should expose public Telegram profile claims."""
        now = datetime.now(UTC)
        payload = {
            "sub": "123456789",
            "telegram_id": 123456789,
            "first_name": "Katrin",
            "last_name": "Example",
            "username": "katrin_dev",
            "language_code": "ru",
            "aud": "postbox",
            "iss": "the-hub-bot",
            "iat": now,
            "exp": now + timedelta(minutes=5),
        }
        token = jwt.encode(payload, hub_secret, algorithm="HS256")

        identity = verify_hub_token(token, hub_secret)

        assert identity.telegram_user_id == 123456789
        assert identity.first_name == "Katrin"
        assert identity.last_name == "Example"
        assert identity.username == "katrin_dev"
        assert identity.language_code == "ru"
        assert identity.profile_claims == frozenset({"first_name", "last_name", "username", "language_code"})

    def test_mismatched_sub_and_telegram_id_rejected(self, hub_secret: str) -> None:
        """telegram_id claim must match sub when both are present."""
        now = datetime.now(UTC)
        payload = {
            "sub": "123456789",
            "telegram_id": 987654321,
            "aud": "postbox",
            "iss": "the-hub-bot",
            "iat": now,
            "exp": now + timedelta(minutes=5),
        }
        token = jwt.encode(payload, hub_secret, algorithm="HS256")

        with pytest.raises(InvalidClaim, match="does not match"):
            verify_hub_token(token, hub_secret)

    def test_invalid_signature_rejected(self, valid_hub_token: str) -> None:
        """Token with wrong signature should be rejected."""
        wrong_secret = "this-is-wrong-secret-not-matching"
        with pytest.raises(InvalidSignature):
            verify_hub_token(valid_hub_token, wrong_secret)

    def test_expired_token_rejected(self, hub_secret: str) -> None:
        """Expired token should be rejected."""
        now = datetime.now(UTC)
        expired_payload = {
            "sub": "123456789",
            "aud": "postbox",
            "iss": "the-hub-bot",
            "iat": now - timedelta(minutes=10),
            "exp": now - timedelta(minutes=5),
        }
        expired_token = jwt.encode(expired_payload, hub_secret, algorithm="HS256")
        with pytest.raises(TokenExpired):
            verify_hub_token(expired_token, hub_secret)

    def test_wrong_audience_rejected(self, hub_secret: str) -> None:
        """Token with wrong audience should be rejected."""
        now = datetime.now(UTC)
        wrong_aud_payload = {
            "sub": "123456789",
            "aud": "laterbox",
            "iss": "the-hub-bot",
            "iat": now,
            "exp": now + timedelta(minutes=5),
        }
        wrong_aud_token = jwt.encode(wrong_aud_payload, hub_secret, algorithm="HS256")
        with pytest.raises(WrongAudience):
            verify_hub_token(wrong_aud_token, hub_secret)

    def test_wrong_issuer_rejected(self, hub_secret: str) -> None:
        """Token with wrong issuer should be rejected."""
        now = datetime.now(UTC)
        wrong_iss_payload = {
            "sub": "123456789",
            "aud": "postbox",
            "iss": "wrong-issuer",
            "iat": now,
            "exp": now + timedelta(minutes=5),
        }
        wrong_iss_token = jwt.encode(wrong_iss_payload, hub_secret, algorithm="HS256")
        with pytest.raises(WrongIssuer):
            verify_hub_token(wrong_iss_token, hub_secret)

    def test_missing_sub_rejected(self, hub_secret: str) -> None:
        """Token without 'sub' claim should be rejected."""
        now = datetime.now(UTC)
        no_sub_payload = {
            "aud": "postbox",
            "iss": "the-hub-bot",
            "iat": now,
            "exp": now + timedelta(minutes=5),
        }
        no_sub_token = jwt.encode(no_sub_payload, hub_secret, algorithm="HS256")
        with pytest.raises(MissingClaim, match="sub"):
            verify_hub_token(no_sub_token, hub_secret)

    def test_invalid_sub_not_integer(self, hub_secret: str) -> None:
        """Token with non-integer 'sub' should be rejected."""
        now = datetime.now(UTC)
        invalid_sub_payload = {
            "sub": "not-a-number",
            "aud": "postbox",
            "iss": "the-hub-bot",
            "iat": now,
            "exp": now + timedelta(minutes=5),
        }
        invalid_sub_token = jwt.encode(invalid_sub_payload, hub_secret, algorithm="HS256")
        with pytest.raises(InvalidClaim, match="sub"):
            verify_hub_token(invalid_sub_token, hub_secret)

    def test_negative_telegram_id_rejected(self, hub_secret: str) -> None:
        """Token with negative telegram_user_id should be rejected."""
        now = datetime.now(UTC)
        negative_id_payload = {
            "sub": "-123",
            "aud": "postbox",
            "iss": "the-hub-bot",
            "iat": now,
            "exp": now + timedelta(minutes=5),
        }
        negative_id_token = jwt.encode(negative_id_payload, hub_secret, algorithm="HS256")
        with pytest.raises(InvalidClaim, match="must be a positive"):
            verify_hub_token(negative_id_token, hub_secret)

    def test_zero_telegram_id_rejected(self, hub_secret: str) -> None:
        """Token with zero telegram_user_id should be rejected."""
        now = datetime.now(UTC)
        zero_id_payload = {
            "sub": "0",
            "aud": "postbox",
            "iss": "the-hub-bot",
            "iat": now,
            "exp": now + timedelta(minutes=5),
        }
        zero_id_token = jwt.encode(zero_id_payload, hub_secret, algorithm="HS256")
        with pytest.raises(InvalidClaim, match="must be a positive"):
            verify_hub_token(zero_id_token, hub_secret)

    def test_missing_secret_raises_error(self, valid_hub_token: str) -> None:
        """Missing or empty secret should raise ValueError."""
        with pytest.raises(ValueError, match="HUB_AUTH_SECRET"):
            verify_hub_token(valid_hub_token, "")

    def test_malformed_token_rejected(self, hub_secret: str) -> None:
        """Malformed token should be rejected."""
        with pytest.raises(InvalidClaim):
            verify_hub_token("not.a.valid.jwt", hub_secret)

    def test_empty_token_rejected(self, hub_secret: str) -> None:
        """Empty token should be rejected."""
        with pytest.raises(InvalidClaim):
            verify_hub_token("", hub_secret)
