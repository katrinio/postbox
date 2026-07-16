from aiogram import Router
from aiogram.types import Message

from postbox.keyboards.main_menu import main_menu_keyboard
from postbox.texts import UNKNOWN_ACTION

router = Router(name=__name__)


async def answer_from_menu(message: Message, text: str) -> None:
    """Reply while keeping the main navigation available."""
    await message.answer(text, reply_markup=main_menu_keyboard())


@router.message()
async def show_unknown_action(message: Message) -> None:
    await answer_from_menu(message, UNKNOWN_ACTION)
