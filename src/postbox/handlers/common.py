from datetime import date, datetime

from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from postbox.models import User


def parse_date(value: str, *, latest: date | None = None) -> date | None:
    try:
        parsed = datetime.strptime(value.strip(), "%d.%m.%Y").date()
    except ValueError:
        return None
    if parsed > (latest or date.today()):
        return None
    return parsed


def format_date(value: date) -> str:
    return value.strftime("%d.%m.%Y")


def normalize_name(value: str) -> str:
    return " ".join(value.split())


def callback_message(callback: CallbackQuery) -> Message | None:
    if isinstance(callback.message, Message):
        return callback.message
    return None


async def register_owner(message: Message, session: AsyncSession) -> User | None:
    telegram_user = message.from_user
    if telegram_user is None:
        return None
    return await User.register(
        session,
        telegram_id=telegram_user.id,
        username=telegram_user.username,
        first_name=telegram_user.first_name,
        last_name=telegram_user.last_name,
        language_code=telegram_user.language_code,
    )


async def owner_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    return await User.find_by_telegram_id(session, telegram_id)
