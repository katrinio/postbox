# ruff: noqa: RUF001

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from postbox.models import Correspondent

CANCEL_RECEIVE = "receive:cancel"
NEW_SENDER = "receive:sender:new"
SENDER_PREFIX = "receive:sender:"
RECEIVED_TODAY = "receive:received:today"
RECEIVED_OTHER = "receive:received:other"
SENT_UNKNOWN = "receive:sent:unknown"
SENT_KNOWN = "receive:sent:known"
CONFIRM_RECEIVE = "receive:confirm"
CHANGE_SENDER = "receive:change:sender"
CHANGE_RECEIVED_DATE = "receive:change:received"
CHANGE_SENT_DATE = "receive:change:sent"


def sender_keyboard(correspondents: list[Correspondent]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=correspondent.name, callback_data=f"{SENDER_PREFIX}{correspondent.id}")]
        for correspondent in correspondents
    ]
    rows.extend(
        [
            [InlineKeyboardButton(text="+ Новый отправитель", callback_data=NEW_SENDER)],
            [InlineKeyboardButton(text="Отмена", callback_data=CANCEL_RECEIVE)],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def received_date_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Сегодня", callback_data=RECEIVED_TODAY)],
            [InlineKeyboardButton(text="Другая дата", callback_data=RECEIVED_OTHER)],
            [InlineKeyboardButton(text="Отмена", callback_data=CANCEL_RECEIVE)],
        ]
    )


def sent_date_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Не знаю", callback_data=SENT_UNKNOWN)],
            [InlineKeyboardButton(text="Указать по штемпелю", callback_data=SENT_KNOWN)],
            [InlineKeyboardButton(text="Отмена", callback_data=CANCEL_RECEIVE)],
        ]
    )


def receive_confirmation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Сохранить", callback_data=CONFIRM_RECEIVE)],
            [InlineKeyboardButton(text="Изменить отправителя", callback_data=CHANGE_SENDER)],
            [
                InlineKeyboardButton(text="Изменить получение", callback_data=CHANGE_RECEIVED_DATE),
                InlineKeyboardButton(text="Изменить отправку", callback_data=CHANGE_SENT_DATE),
            ],
            [InlineKeyboardButton(text="Отмена", callback_data=CANCEL_RECEIVE)],
        ]
    )
