from aiogram import F, Router
from aiogram.types import Message

from postbox.keyboards.main_menu import MainMenuAction, main_menu_keyboard
from postbox.texts import JOURNAL_PLACEHOLDER, RECEIVE_PLACEHOLDER, SEND_PLACEHOLDER, UNKNOWN_ACTION

router = Router(name=__name__)


async def answer_from_menu(message: Message, text: str) -> None:
    """Reply while keeping the main navigation available."""
    await message.answer(text, reply_markup=main_menu_keyboard())


@router.message(F.text == MainMenuAction.SEND)
async def begin_send(message: Message) -> None:
    await answer_from_menu(message, SEND_PLACEHOLDER)


@router.message(F.text == MainMenuAction.RECEIVE)
async def begin_receive(message: Message) -> None:
    await answer_from_menu(message, RECEIVE_PLACEHOLDER)


@router.message(F.text == MainMenuAction.JOURNAL)
async def show_journal(message: Message) -> None:
    await answer_from_menu(message, JOURNAL_PLACEHOLDER)


@router.message()
async def show_unknown_action(message: Message) -> None:
    await answer_from_menu(message, UNKNOWN_ACTION)
