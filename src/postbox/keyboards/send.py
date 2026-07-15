from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from postbox.models import Correspondent

CANCEL_SEND = "send:cancel"
NEW_RECIPIENT = "send:recipient:new"
RECIPIENT_PREFIX = "send:recipient:"
DATE_TODAY = "send:date:today"
DATE_OTHER = "send:date:other"
CONFIRM_SEND = "send:confirm"
CHANGE_RECIPIENT = "send:change:recipient"
CHANGE_DATE = "send:change:date"


def recipient_keyboard(correspondents: list[Correspondent]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=correspondent.name, callback_data=f"{RECIPIENT_PREFIX}{correspondent.id}")]
        for correspondent in correspondents
    ]
    rows.extend(
        [
            [InlineKeyboardButton(text="+ Новый получатель", callback_data=NEW_RECIPIENT)],
            [InlineKeyboardButton(text="Отмена", callback_data=CANCEL_SEND)],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def date_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Сегодня", callback_data=DATE_TODAY)],
            [InlineKeyboardButton(text="Другая дата", callback_data=DATE_OTHER)],
            [InlineKeyboardButton(text="Отмена", callback_data=CANCEL_SEND)],
        ]
    )


def confirmation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Сохранить", callback_data=CONFIRM_SEND)],
            [
                InlineKeyboardButton(text="Изменить получателя", callback_data=CHANGE_RECIPIENT),
                InlineKeyboardButton(text="Изменить дату", callback_data=CHANGE_DATE),
            ],
            [InlineKeyboardButton(text="Отмена", callback_data=CANCEL_SEND)],
        ]
    )
