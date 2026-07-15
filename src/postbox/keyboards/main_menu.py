from enum import StrEnum

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


class MainMenuAction(StrEnum):
    SEND = "📮 Отправить"
    RECEIVE = "📬 Получить"
    JOURNAL = "📚 Посмотреть почту"


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Build the persistent entry point to every Postbox flow."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=MainMenuAction.SEND),
                KeyboardButton(text=MainMenuAction.RECEIVE),
            ],
            [KeyboardButton(text=MainMenuAction.JOURNAL)],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Выбери действие",
    )
