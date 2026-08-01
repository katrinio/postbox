"""User synchronization from verified Hub Bot claims."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from postbox.auth.hub import HubIdentity
from postbox.models import User

logger = logging.getLogger(__name__)


def _has_claim(identity: HubIdentity, claim: str) -> bool:
    return claim in identity.profile_claims


async def sync_user_from_hub_claims(session: AsyncSession, identity: HubIdentity) -> User:
    """Create or update a local user from already verified Hub JWT claims."""
    user = await User.find_by_telegram_id(session, identity.telegram_user_id)

    if user is None:
        first_name = (
            identity.first_name if _has_claim(identity, "first_name") and identity.first_name else "Telegram User"
        )
        user = await User.create(
            session,
            telegram_id=identity.telegram_user_id,
            username=identity.username if _has_claim(identity, "username") else None,
            first_name=first_name,
            last_name=identity.last_name if _has_claim(identity, "last_name") else None,
            language_code=identity.language_code if _has_claim(identity, "language_code") else None,
            approved_at=None,
        )
        logger.info("Hub auth: created new user for telegram_id=%d", identity.telegram_user_id)
        return user

    if _has_claim(identity, "first_name") and identity.first_name:
        user.first_name = identity.first_name
    if _has_claim(identity, "last_name"):
        user.last_name = identity.last_name
    if _has_claim(identity, "username"):
        user.username = identity.username
    if _has_claim(identity, "language_code"):
        user.language_code = identity.language_code

    await user.save(session)
    logger.info("Hub auth: synced existing user for telegram_id=%d", identity.telegram_user_id)
    return user
