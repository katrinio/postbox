from datetime import date
from html import escape

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from sqlalchemy.ext.asyncio import AsyncSession

from postbox.handlers.common import callback_message, format_date, normalize_name, parse_date, register_owner
from postbox.keyboards.main_menu import MainMenuAction, main_menu_keyboard
from postbox.keyboards.receive import (
    CANCEL_RECEIVE,
    CHANGE_RECEIVED_DATE,
    CHANGE_SENDER,
    CHANGE_SENT_DATE,
    CONFIRM_RECEIVE,
    NEW_SENDER,
    RECEIVED_OTHER,
    RECEIVED_TODAY,
    SENDER_PREFIX,
    SENT_KNOWN,
    SENT_UNKNOWN,
    receive_confirmation_keyboard,
    received_date_keyboard,
    sender_keyboard,
    sent_date_keyboard,
)
from postbox.models import Correspondent, MailDirection, MailItem
from postbox.texts import (
    RECEIVE_CANCELLED,
    RECEIVE_DATE,
    RECEIVE_DATE_CUSTOM,
    RECEIVE_DATE_INVALID,
    RECEIVE_EXPIRED,
    RECEIVE_NEW_SENDER,
    RECEIVE_SAVED,
    RECEIVE_SENDER,
    RECEIVE_SENDER_INVALID,
    RECEIVE_SENT_DATE,
    RECEIVE_SENT_DATE_CUSTOM,
    RECEIVE_SENT_DATE_INVALID,
    RECEIVE_USE_BUTTONS,
)

router = Router(name=__name__)


class ReceiveMail(StatesGroup):
    choosing_sender = State()
    entering_sender = State()
    choosing_received_date = State()
    entering_received_date = State()
    choosing_sent_date = State()
    entering_sent_date = State()
    confirming = State()


def receive_confirmation_text(
    sender_name: str,
    *,
    sent_at: date | None,
    received_at: date,
) -> str:
    sent = format_date(sent_at) if sent_at is not None else "неизвестно"
    return (
        "Проверим запись:\n\n"
        f"От кого: <b>{escape(sender_name)}</b>\n"
        f"Отправлено: <b>{sent}</b>\n"
        f"Получено: <b>{format_date(received_at)}</b>\n"
        "Статус: <b>получено</b>"
    )


async def show_sent_date_question(message: Message, state: FSMContext) -> None:
    await state.set_state(ReceiveMail.choosing_sent_date)
    await message.answer(RECEIVE_SENT_DATE, reply_markup=sent_date_keyboard())


async def show_receive_confirmation(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    sender_name = str(data["sender_name"])
    received_at = date.fromisoformat(str(data["received_at"]))
    sent_at_value = data.get("sent_at")
    sent_at = date.fromisoformat(str(sent_at_value)) if sent_at_value is not None else None
    await state.set_state(ReceiveMail.confirming)
    await message.answer(
        receive_confirmation_text(sender_name, sent_at=sent_at, received_at=received_at),
        reply_markup=receive_confirmation_keyboard(),
    )


@router.message(F.text == MainMenuAction.RECEIVE)
async def begin_receive(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    owner = await register_owner(message, session)
    if owner is None:
        await message.answer(RECEIVE_EXPIRED, reply_markup=main_menu_keyboard())
        return

    correspondents = await Correspondent.for_owner(session, owner.id)
    await state.update_data(owner_id=owner.id)
    await state.set_state(ReceiveMail.choosing_sender)
    await message.answer(RECEIVE_SENDER, reply_markup=ReplyKeyboardRemove())
    await message.answer(RECEIVE_USE_BUTTONS, reply_markup=sender_keyboard(correspondents))


@router.callback_query(ReceiveMail.choosing_sender, F.data == NEW_SENDER)
async def request_new_sender(callback: CallbackQuery, state: FSMContext) -> None:
    message = callback_message(callback)
    if message is None:
        await callback.answer(RECEIVE_EXPIRED, show_alert=True)
        return
    await callback.answer()
    await state.set_state(ReceiveMail.entering_sender)
    await message.edit_text(RECEIVE_NEW_SENDER)


@router.callback_query(
    ReceiveMail.choosing_sender,
    F.data.startswith(SENDER_PREFIX) & (F.data != NEW_SENDER),
)
async def choose_sender(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    message = callback_message(callback)
    if message is None or callback.data is None:
        await callback.answer(RECEIVE_EXPIRED, show_alert=True)
        return

    try:
        correspondent_id = int(callback.data.removeprefix(SENDER_PREFIX))
        owner_id = int((await state.get_data())["owner_id"])
    except KeyError, TypeError, ValueError:
        await callback.answer(RECEIVE_EXPIRED, show_alert=True)
        return

    correspondent = await Correspondent.find_for_owner(
        session,
        owner_id=owner_id,
        correspondent_id=correspondent_id,
    )
    if correspondent is None:
        await callback.answer(RECEIVE_EXPIRED, show_alert=True)
        return

    await callback.answer()
    await state.update_data(correspondent_id=correspondent.id, sender_name=correspondent.name)
    await state.set_state(ReceiveMail.choosing_received_date)
    await message.edit_text(RECEIVE_DATE, reply_markup=received_date_keyboard())


@router.message(ReceiveMail.entering_sender, F.text)
async def accept_new_sender(message: Message, state: FSMContext) -> None:
    name = normalize_name(message.text or "")
    if not 1 <= len(name) <= 160:
        await message.answer(RECEIVE_SENDER_INVALID)
        return

    await state.update_data(correspondent_id=None, sender_name=name)
    await state.set_state(ReceiveMail.choosing_received_date)
    await message.answer(RECEIVE_DATE, reply_markup=received_date_keyboard())


@router.callback_query(ReceiveMail.choosing_received_date, F.data == RECEIVED_TODAY)
async def receive_today(callback: CallbackQuery, state: FSMContext) -> None:
    message = callback_message(callback)
    if message is None:
        await callback.answer(RECEIVE_EXPIRED, show_alert=True)
        return
    await callback.answer()
    await state.update_data(received_at=date.today().isoformat(), sent_at=None)
    await message.edit_reply_markup(reply_markup=None)
    await show_sent_date_question(message, state)


@router.callback_query(ReceiveMail.choosing_received_date, F.data == RECEIVED_OTHER)
async def request_received_date(callback: CallbackQuery, state: FSMContext) -> None:
    message = callback_message(callback)
    if message is None:
        await callback.answer(RECEIVE_EXPIRED, show_alert=True)
        return
    await callback.answer()
    await state.set_state(ReceiveMail.entering_received_date)
    await message.edit_text(RECEIVE_DATE_CUSTOM)


@router.message(ReceiveMail.entering_received_date, F.text)
async def accept_received_date(message: Message, state: FSMContext) -> None:
    received_at = parse_date(message.text or "")
    if received_at is None:
        await message.answer(RECEIVE_DATE_INVALID)
        return

    await state.update_data(received_at=received_at.isoformat(), sent_at=None)
    await show_sent_date_question(message, state)


@router.callback_query(ReceiveMail.choosing_sent_date, F.data == SENT_UNKNOWN)
async def choose_unknown_sent_date(callback: CallbackQuery, state: FSMContext) -> None:
    message = callback_message(callback)
    if message is None:
        await callback.answer(RECEIVE_EXPIRED, show_alert=True)
        return
    await callback.answer()
    await state.update_data(sent_at=None)
    await message.edit_reply_markup(reply_markup=None)
    await show_receive_confirmation(message, state)


@router.callback_query(ReceiveMail.choosing_sent_date, F.data == SENT_KNOWN)
async def request_sent_date(callback: CallbackQuery, state: FSMContext) -> None:
    message = callback_message(callback)
    if message is None:
        await callback.answer(RECEIVE_EXPIRED, show_alert=True)
        return
    await callback.answer()
    await state.set_state(ReceiveMail.entering_sent_date)
    await message.edit_text(RECEIVE_SENT_DATE_CUSTOM)


@router.message(ReceiveMail.entering_sent_date, F.text)
async def accept_sent_date(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    try:
        received_at = date.fromisoformat(str(data["received_at"]))
    except KeyError, ValueError:
        await state.clear()
        await message.answer(RECEIVE_EXPIRED, reply_markup=main_menu_keyboard())
        return

    sent_at = parse_date(message.text or "", latest=received_at)
    if sent_at is None:
        await message.answer(RECEIVE_SENT_DATE_INVALID)
        return

    await state.update_data(sent_at=sent_at.isoformat())
    await show_receive_confirmation(message, state)


@router.callback_query(ReceiveMail.confirming, F.data == CHANGE_SENDER)
async def change_sender(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    message = callback_message(callback)
    if message is None:
        await callback.answer(RECEIVE_EXPIRED, show_alert=True)
        return
    try:
        owner_id = int((await state.get_data())["owner_id"])
    except KeyError, TypeError, ValueError:
        await callback.answer(RECEIVE_EXPIRED, show_alert=True)
        return

    correspondents = await Correspondent.for_owner(session, owner_id)
    await callback.answer()
    await state.update_data(correspondent_id=None, sender_name=None)
    await state.set_state(ReceiveMail.choosing_sender)
    await message.edit_text(RECEIVE_SENDER, reply_markup=sender_keyboard(correspondents))


@router.callback_query(ReceiveMail.confirming, F.data == CHANGE_RECEIVED_DATE)
async def change_received_date(callback: CallbackQuery, state: FSMContext) -> None:
    message = callback_message(callback)
    if message is None:
        await callback.answer(RECEIVE_EXPIRED, show_alert=True)
        return
    await callback.answer()
    await state.update_data(received_at=None, sent_at=None)
    await state.set_state(ReceiveMail.choosing_received_date)
    await message.edit_text(RECEIVE_DATE, reply_markup=received_date_keyboard())


@router.callback_query(ReceiveMail.confirming, F.data == CHANGE_SENT_DATE)
async def change_sent_date(callback: CallbackQuery, state: FSMContext) -> None:
    message = callback_message(callback)
    if message is None:
        await callback.answer(RECEIVE_EXPIRED, show_alert=True)
        return
    await callback.answer()
    await state.update_data(sent_at=None)
    await state.set_state(ReceiveMail.choosing_sent_date)
    await message.edit_text(RECEIVE_SENT_DATE, reply_markup=sent_date_keyboard())


@router.callback_query(ReceiveMail.confirming, F.data == CONFIRM_RECEIVE)
async def confirm_receive(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    message = callback_message(callback)
    if message is None:
        await callback.answer(RECEIVE_EXPIRED, show_alert=True)
        return

    data = await state.get_data()
    try:
        owner_id = int(data["owner_id"])
        sender_name = str(data["sender_name"])
        received_at = date.fromisoformat(str(data["received_at"]))
        sent_at_value = data.get("sent_at")
        sent_at = date.fromisoformat(str(sent_at_value)) if sent_at_value is not None else None
    except KeyError, TypeError, ValueError:
        await callback.answer(RECEIVE_EXPIRED, show_alert=True)
        await state.clear()
        return

    correspondent_id = data.get("correspondent_id")
    correspondent: Correspondent | None
    if correspondent_id is None:
        correspondent = await Correspondent.find_or_create(session, owner_id=owner_id, name=sender_name)
    else:
        correspondent = await Correspondent.find_for_owner(
            session,
            owner_id=owner_id,
            correspondent_id=int(correspondent_id),
        )
        if correspondent is None:
            await callback.answer(RECEIVE_EXPIRED, show_alert=True)
            await state.clear()
            return

    await MailItem.create(
        session,
        owner_id=owner_id,
        correspondent_id=correspondent.id,
        direction=MailDirection.INCOMING,
        sent_at=sent_at,
        received_at=received_at,
    )
    await state.clear()
    await callback.answer()
    await message.edit_text(
        f"{RECEIVE_SAVED}\n\n"
        f"От кого: <b>{escape(correspondent.name)}</b>\n"
        f"Отправлено: <b>{format_date(sent_at) if sent_at else 'неизвестно'}</b>\n"
        f"Получено: <b>{format_date(received_at)}</b>\n"
        "Статус: <b>получено</b>"
    )
    await message.answer("Что будем делать?", reply_markup=main_menu_keyboard())


@router.callback_query(F.data == CANCEL_RECEIVE)
async def cancel_receive(callback: CallbackQuery, state: FSMContext) -> None:
    message = callback_message(callback)
    await state.clear()
    if message is None:
        await callback.answer(RECEIVE_CANCELLED, show_alert=True)
        return
    await callback.answer()
    await message.edit_text(RECEIVE_CANCELLED)
    await message.answer("Что будем делать?", reply_markup=main_menu_keyboard())


@router.message(StateFilter(ReceiveMail))
async def request_receive_action(message: Message) -> None:
    await message.answer(RECEIVE_USE_BUTTONS, reply_markup=ReplyKeyboardRemove())
