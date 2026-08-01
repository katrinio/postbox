"""Hub Bot JWT verification for authentication handoff."""

from __future__ import annotations

from dataclasses import dataclass

import jwt


class HubAuthError(ValueError):
    """Base exception for Hub authentication errors."""


class InvalidSignature(HubAuthError):
    """JWT signature verification failed."""


class TokenExpired(HubAuthError):
    """JWT token has expired."""


class WrongAudience(HubAuthError):
    """JWT audience claim does not match expected value."""


class WrongIssuer(HubAuthError):
    """JWT issuer claim does not match expected value."""


class MissingClaim(HubAuthError):
    """JWT is missing a required claim."""


class InvalidClaim(HubAuthError):
    """JWT claim has an invalid value."""


@dataclass(frozen=True)
class HubIdentity:
    """Verified identity from Hub Bot JWT token."""

    telegram_user_id: int
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None
    language_code: str | None = None
    profile_claims: frozenset[str] = frozenset()


PROFILE_CLAIMS = frozenset({"first_name", "last_name", "username", "language_code"})


def _optional_string_claim(payload: dict, claim: str) -> str | None:
    value = payload.get(claim)
    if value is None:
        return None
    if not isinstance(value, str):
        raise InvalidClaim(f"{claim} claim must be a string or null")
    value = value.strip()
    return value or None


def verify_hub_token(token: str, secret: str) -> HubIdentity:
    """Verify and extract identity from Hub Bot JWT token.

    Args:
        token: JWT token from The Hub Bot
        secret: Shared secret key (HS256 HMAC)

    Returns:
        HubIdentity with extracted telegram_user_id

    Raises:
        InvalidSignature: Signature verification failed
        TokenExpired: Token has expired
        WrongAudience: Audience is not 'postbox'
        WrongIssuer: Issuer is not 'the-hub-bot'
        MissingClaim: Required claim is missing
        InvalidClaim: Claim has invalid value
        ValueError: Secret is empty or malformed token
    """
    if not secret or not secret.strip():
        raise ValueError("HUB_AUTH_SECRET must not be empty")

    if not token or not token.strip():
        raise InvalidClaim("Token cannot be empty")

    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience="postbox",
            issuer="the-hub-bot",
        )
    except jwt.InvalidSignatureError as e:
        raise InvalidSignature("Signature verification failed") from e
    except jwt.ExpiredSignatureError as e:
        raise TokenExpired("Token has expired") from e
    except jwt.InvalidAudienceError as e:
        raise WrongAudience("Audience claim does not match 'postbox'") from e
    except jwt.InvalidIssuerError as e:
        raise WrongIssuer("Issuer claim does not match 'the-hub-bot'") from e
    except jwt.MissingRequiredClaimError as e:
        raise MissingClaim(f"Missing required claim: {e.claim}") from e
    except jwt.DecodeError as e:
        raise InvalidClaim("Token is malformed or invalid") from e
    except jwt.InvalidTokenError as e:
        raise InvalidClaim(f"Token validation failed: {type(e).__name__}") from e

    # Validate and extract sub claim (telegram_user_id)
    sub_claim = payload.get("sub")
    if sub_claim is None:
        raise MissingClaim("sub claim is missing")

    try:
        telegram_user_id = int(sub_claim)
    except (TypeError, ValueError) as e:
        raise InvalidClaim(f"sub claim must be a positive integer, got {sub_claim}") from e

    if telegram_user_id <= 0:
        raise InvalidClaim("sub (telegram_user_id) must be a positive integer")

    telegram_id_claim = payload.get("telegram_id")
    if telegram_id_claim is not None:
        try:
            claimed_telegram_id = int(telegram_id_claim)
        except (TypeError, ValueError) as e:
            raise InvalidClaim("telegram_id claim must be a positive integer") from e
        if claimed_telegram_id <= 0:
            raise InvalidClaim("telegram_id claim must be a positive integer")
        if claimed_telegram_id != telegram_user_id:
            raise InvalidClaim("telegram_id claim does not match sub")

    present_profile_claims = frozenset(claim for claim in PROFILE_CLAIMS if claim in payload)

    return HubIdentity(
        telegram_user_id=telegram_user_id,
        first_name=_optional_string_claim(payload, "first_name"),
        last_name=_optional_string_claim(payload, "last_name"),
        username=_optional_string_claim(payload, "username"),
        language_code=_optional_string_claim(payload, "language_code"),
        profile_claims=present_profile_claims,
    )
