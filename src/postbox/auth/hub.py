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

    return HubIdentity(telegram_user_id=telegram_user_id)
