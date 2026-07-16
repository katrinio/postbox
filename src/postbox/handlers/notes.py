from html import escape

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from postbox.handlers.common import callback_message, owner_by_telegram_id
from postbox.handlers.journal import journal_detail_text
from postbox.keyboards.journal import journal_detail_keyboard
from postbox.keyboards.notes import (
    CANCEL_NOTE,
    CHANGE_NOTE,
    CONFIRM_NOTE,
    CONFIRM_NOTE_DELETE,
    DELETE_NOTE_PREFIX,
    EDIT_NOTE_PREFIX,
    note_confirmation_keyboard,
    note_delete_confirmation_keyboard,
    note_input_keyboard,
)
from postbox.models import MailItem, MailJournalFilter, MailNoteError
from postbox.texts import (
    NOTE_CONFIRMATION,
    NOTE_DELETE_CONFIRMATION,
    NOTE_EXPIRED,
    NOTE_INPUT,
    NOTE_INVALID,
    NOTE_USE_BUTTONS,
)

router = Router(name=__name__)


class EditNote(StatesGroup):
    entering = State()
    confirming = State()
    confirming_delete = State()


def note_confirmation_text(note: str) -> str:
    return NOTE_CONFIRMATION.format(note=escape(note))


def parse_note_callback(data: str, prefix: str) -> tuple[int, MailJournalFilter, int] | None:
    try:
        actual_prefix, mail_id, view_value, page_value = data.rsplit(":", 3)
        if f"{actual_prefix}:" != prefix:
            return None
        return int(mail_id), MailJournalFilter(view_value), int(page_value)
    except ValueError:
        return None


async def load_note_mail(
    telegram_id: int,
    state: FSMContext,
    session: AsyncSession,
) -> tuple[MailItem, MailJournalFilter, int] | None:
    owner = await owner_by_telegram_id(session, telegram_id)
    data = await state.get_data()
    if owner is None:
        return None
    try:
        mail_id = int(data["mail_id"])
        view = MailJournalFilter(str(data["view"]))
        page = int(data["page"])
    except KeyError, TypeError, ValueError:
        return None
    mail = await MailItem.find_for_owner(session, owner_id=owner.id, mail_id=mail_id)
    if mail is None:
        return None
    return mail, view, page


async def start_note_action(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    *,
    prefix: str,
) -> tuple[Message, MailItem] | None:
    message = callback_message(callback)
    parsed = parse_note_callback(callback.data or "", prefix)
    owner = await owner_by_telegram_id(session, callback.from_user.id)
    if message is None or parsed is None or owner is None:
        await callback.answer(NOTE_EXPIRED, show_alert=True)
        return None
    mail_id, view, page = parsed
    mail = await MailItem.find_for_owner(session, owner_id=owner.id, mail_id=mail_id)
    if mail is None:
        await callback.answer(NOTE_EXPIRED, show_alert=True)
        return None
    await state.clear()
    await state.update_data(mail_id=mail.id, view=view.value, page=page)
    return message, mail


async def show_note_input(message: Message, state: FSMContext, mail: MailItem) -> None:
    await state.set_state(EditNote.entering)
    await message.edit_text(NOTE_INPUT, reply_markup=note_input_keyboard(can_delete=mail.note is not None))


@router.callback_query(F.data.startswith(EDIT_NOTE_PREFIX))
async def begin_note_edit(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    started = await start_note_action(callback, state, session, prefix=EDIT_NOTE_PREFIX)
    if started is None:
        return
    message, mail = started
    await callback.answer()
    await show_note_input(message, state, mail)


@router.message(EditNote.entering, F.text)
async def accept_note(message: Message, state: FSMContext) -> None:
    try:
        note = MailItem.normalize_note(message.text or "")
    except MailNoteError:
        await message.answer(NOTE_INVALID)
        return
    await state.update_data(note=note)
    await state.set_state(EditNote.confirming)
    await message.answer(
        note_confirmation_text(note),
        reply_markup=note_confirmation_keyboard(),
    )


@router.callback_query(EditNote.confirming, F.data == CHANGE_NOTE)
async def change_note(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    message = callback_message(callback)
    loaded = await load_note_mail(callback.from_user.id, state, session)
    if message is None or loaded is None:
        await callback.answer(NOTE_EXPIRED, show_alert=True)
        await state.clear()
        return
    mail, _, _ = loaded
    await state.update_data(note=None)
    await callback.answer()
    await show_note_input(message, state, mail)


@router.callback_query(EditNote.confirming, F.data == CONFIRM_NOTE)
async def confirm_note(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    message = callback_message(callback)
    loaded = await load_note_mail(callback.from_user.id, state, session)
    data = await state.get_data()
    if message is None or loaded is None:
        await callback.answer(NOTE_EXPIRED, show_alert=True)
        await state.clear()
        return
    note = data.get("note")
    if not isinstance(note, str):
        await callback.answer(NOTE_EXPIRED, show_alert=True)
        await state.clear()
        return
    mail, view, page = loaded
    try:
        await mail.set_note(session, note=note)
    except MailNoteError:
        await callback.answer(NOTE_INVALID, show_alert=True)
        return
    await state.clear()
    await callback.answer()
    await message.edit_text(
        journal_detail_text(mail),
        reply_markup=journal_detail_keyboard(mail, view, page),
    )


async def show_delete_confirmation(message: Message, state: FSMContext) -> None:
    await state.set_state(EditNote.confirming_delete)
    await message.edit_text(NOTE_DELETE_CONFIRMATION, reply_markup=note_delete_confirmation_keyboard())


@router.callback_query(F.data.startswith(DELETE_NOTE_PREFIX))
async def begin_note_delete(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    started = await start_note_action(callback, state, session, prefix=DELETE_NOTE_PREFIX)
    if started is None:
        return
    message, mail = started
    if mail.note is None:
        await callback.answer(NOTE_EXPIRED, show_alert=True)
        await state.clear()
        return
    await callback.answer()
    await show_delete_confirmation(message, state)


@router.callback_query(EditNote.entering, F.data == CONFIRM_NOTE_DELETE)
async def request_note_delete(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    message = callback_message(callback)
    loaded = await load_note_mail(callback.from_user.id, state, session)
    if message is None or loaded is None or loaded[0].note is None:
        await callback.answer(NOTE_EXPIRED, show_alert=True)
        await state.clear()
        return
    await callback.answer()
    await show_delete_confirmation(message, state)


@router.callback_query(EditNote.confirming_delete, F.data == CONFIRM_NOTE_DELETE)
async def confirm_note_delete(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    message = callback_message(callback)
    loaded = await load_note_mail(callback.from_user.id, state, session)
    if message is None or loaded is None:
        await callback.answer(NOTE_EXPIRED, show_alert=True)
        await state.clear()
        return
    mail, view, page = loaded
    await mail.set_note(session, note=None)
    await state.clear()
    await callback.answer()
    await message.edit_text(
        journal_detail_text(mail),
        reply_markup=journal_detail_keyboard(mail, view, page),
    )


async def restore_mail_detail(
    telegram_id: int,
    state: FSMContext,
    session: AsyncSession,
) -> tuple[str, InlineKeyboardMarkup] | None:
    loaded = await load_note_mail(telegram_id, state, session)
    if loaded is None:
        return None
    mail, view, page = loaded
    return journal_detail_text(mail), journal_detail_keyboard(mail, view, page)


@router.callback_query(F.data == CANCEL_NOTE)
async def cancel_note(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    message = callback_message(callback)
    restored = await restore_mail_detail(callback.from_user.id, state, session)
    await state.clear()
    if message is None or restored is None:
        await callback.answer(NOTE_EXPIRED, show_alert=True)
        return
    text, keyboard = restored
    await callback.answer()
    await message.edit_text(text, reply_markup=keyboard)


@router.message(StateFilter(EditNote), Command("cancel"))
async def cancel_note_command(message: Message, state: FSMContext, session: AsyncSession) -> None:
    telegram_user = message.from_user
    restored = None if telegram_user is None else await restore_mail_detail(telegram_user.id, state, session)
    await state.clear()
    if restored is None:
        await message.answer(NOTE_EXPIRED)
        return
    text, keyboard = restored
    await message.answer(text, reply_markup=keyboard)


@router.message(StateFilter(EditNote))
async def request_note_action(message: Message) -> None:
    await message.answer(NOTE_USE_BUTTONS)
