from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from postbox.keyboards.main_menu import main_menu_keyboard
from postbox.models import User
from postbox.texts import WELCOME

router = Router(name=__name__)


@router.message(CommandStart())
async def show_start(message: Message, session: AsyncSession) -> None:
    """Welcome the user and reveal the main menu."""
    telegram_user = message.from_user
    if telegram_user is not None:
        await User.register(
            session,
            telegram_id=telegram_user.id,
            username=telegram_user.username,
            first_name=telegram_user.first_name,
            last_name=telegram_user.last_name,
            language_code=telegram_user.language_code,
        )

    await message.answer(WELCOME, reply_markup=main_menu_keyboard())
