from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from postbox.keyboards.main_menu import main_menu_keyboard
from postbox.texts import WELCOME

router = Router(name=__name__)


@router.message(CommandStart())
async def show_start(message: Message) -> None:
    """Welcome the user and reveal the main menu."""
    await message.answer(WELCOME, reply_markup=main_menu_keyboard())
