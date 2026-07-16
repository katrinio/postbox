from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from postbox.models import MailJournalFilter

EDIT_NOTE_PREFIX = "note:edit:"
DELETE_NOTE_PREFIX = "note:delete:"
CONFIRM_NOTE = "note:confirm"
CHANGE_NOTE = "note:change"
CONFIRM_NOTE_DELETE = "note:confirm:delete"
CANCEL_NOTE = "note:cancel"


def edit_note_callback(mail_id: int, view: MailJournalFilter, page: int) -> str:
    return f"{EDIT_NOTE_PREFIX}{mail_id}:{view.value}:{page}"


def delete_note_callback(mail_id: int, view: MailJournalFilter, page: int) -> str:
    return f"{DELETE_NOTE_PREFIX}{mail_id}:{view.value}:{page}"


def note_input_keyboard(*, can_delete: bool) -> InlineKeyboardMarkup:
    rows = []
    if can_delete:
        rows.append([InlineKeyboardButton(text="Убрать заметку", callback_data=CONFIRM_NOTE_DELETE)])
    rows.append([InlineKeyboardButton(text="Отмена", callback_data=CANCEL_NOTE)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def note_confirmation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Сохранить", callback_data=CONFIRM_NOTE)],
            [InlineKeyboardButton(text="Изменить текст", callback_data=CHANGE_NOTE)],
            [InlineKeyboardButton(text="Отмена", callback_data=CANCEL_NOTE)],
        ]
    )


def note_delete_confirmation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Да, убрать", callback_data=CONFIRM_NOTE_DELETE)],
            [InlineKeyboardButton(text="Отмена", callback_data=CANCEL_NOTE)],
        ]
    )
