from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from postbox.models import MailJournalFilter

MARK_RECEIVED_PREFIX = "delivery:mark:"
DELIVERY_TODAY = "delivery:date:today"
DELIVERY_OTHER = "delivery:date:other"
CONFIRM_DELIVERY = "delivery:confirm"
CHANGE_DELIVERY_DATE = "delivery:change:date"
CANCEL_DELIVERY = "delivery:cancel"


def mark_received_callback(mail_id: int, view: MailJournalFilter, page: int) -> str:
    return f"{MARK_RECEIVED_PREFIX}{mail_id}:{view.value}:{page}"


def delivery_date_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Сегодня", callback_data=DELIVERY_TODAY)],
            [InlineKeyboardButton(text="Другая дата", callback_data=DELIVERY_OTHER)],
            [InlineKeyboardButton(text="Отмена", callback_data=CANCEL_DELIVERY)],
        ]
    )


def delivery_confirmation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Сохранить", callback_data=CONFIRM_DELIVERY)],
            [InlineKeyboardButton(text="Изменить дату", callback_data=CHANGE_DELIVERY_DATE)],
            [InlineKeyboardButton(text="Отмена", callback_data=CANCEL_DELIVERY)],
        ]
    )
