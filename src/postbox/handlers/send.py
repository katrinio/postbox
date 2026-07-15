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
from postbox.keyboards.send import (
    CANCEL_SEND,
    CHANGE_DATE,
    CHANGE_RECIPIENT,
    CONFIRM_SEND,
    DATE_OTHER,
    DATE_TODAY,
    NEW_RECIPIENT,
    RECIPIENT_PREFIX,
    confirmation_keyboard,
    date_keyboard,
    recipient_keyboard,
)
from postbox.models import Correspondent, MailDirection, MailItem
from postbox.texts import (
    SEND_CANCELLED,
    SEND_DATE,
    SEND_DATE_CUSTOM,
    SEND_DATE_INVALID,
    SEND_EXPIRED,
    SEND_NEW_RECIPIENT,
    SEND_RECIPIENT,
    SEND_RECIPIENT_INVALID,
    SEND_SAVED,
    SEND_USE_BUTTONS,
)

router = Router(name=__name__)


class SendMail(StatesGroup):
    choosing_recipient = State()
    entering_recipient = State()
    choosing_date = State()
    entering_date = State()
    confirming = State()


def parse_sent_date(value: str, *, today: date | None = None) -> date | None:
    return parse_date(value, latest=today)


def confirmation_text(recipient_name: str, sent_at: date) -> str:
    return (
        "Проверим запись:\n\n"
        f"Кому: <b>{escape(recipient_name)}</b>\n"
        f"Отправлено: <b>{format_date(sent_at)}</b>\n"
        "Статус: <b>в пути</b>"
    )


async def show_confirmation(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    recipient_name = str(data["recipient_name"])
    sent_at = date.fromisoformat(str(data["sent_at"]))
    await state.set_state(SendMail.confirming)
    await message.answer(
        confirmation_text(recipient_name, sent_at),
        reply_markup=confirmation_keyboard(),
    )


@router.message(F.text == MainMenuAction.SEND)
async def begin_send(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    owner = await register_owner(message, session)
    if owner is None:
        await message.answer(SEND_EXPIRED, reply_markup=main_menu_keyboard())
        return

    correspondents = await Correspondent.for_owner(session, owner.id)
    await state.update_data(owner_id=owner.id)
    await state.set_state(SendMail.choosing_recipient)
    await message.answer(
        SEND_RECIPIENT,
        reply_markup=ReplyKeyboardRemove(),
    )
    await message.answer(SEND_USE_BUTTONS, reply_markup=recipient_keyboard(correspondents))


@router.callback_query(SendMail.choosing_recipient, F.data == NEW_RECIPIENT)
async def request_new_recipient(callback: CallbackQuery, state: FSMContext) -> None:
    message = callback_message(callback)
    if message is None:
        await callback.answer(SEND_EXPIRED, show_alert=True)
        return
    await callback.answer()
    await state.set_state(SendMail.entering_recipient)
    await message.edit_text(SEND_NEW_RECIPIENT)


@router.callback_query(
    SendMail.choosing_recipient,
    F.data.startswith(RECIPIENT_PREFIX) & (F.data != NEW_RECIPIENT),
)
async def choose_recipient(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    message = callback_message(callback)
    if message is None or callback.data is None:
        await callback.answer(SEND_EXPIRED, show_alert=True)
        return

    try:
        correspondent_id = int(callback.data.removeprefix(RECIPIENT_PREFIX))
        owner_id = int((await state.get_data())["owner_id"])
    except KeyError, TypeError, ValueError:
        await callback.answer(SEND_EXPIRED, show_alert=True)
        return

    correspondent = await Correspondent.find_for_owner(
        session,
        owner_id=owner_id,
        correspondent_id=correspondent_id,
    )
    if correspondent is None:
        await callback.answer(SEND_EXPIRED, show_alert=True)
        return

    await callback.answer()
    await state.update_data(
        correspondent_id=correspondent.id,
        recipient_name=correspondent.name,
    )
    await state.set_state(SendMail.choosing_date)
    await message.edit_text(SEND_DATE, reply_markup=date_keyboard())


@router.message(SendMail.entering_recipient, F.text)
async def accept_new_recipient(message: Message, state: FSMContext) -> None:
    name = normalize_name(message.text or "")
    if not 1 <= len(name) <= 160:
        await message.answer(SEND_RECIPIENT_INVALID)
        return

    await state.update_data(correspondent_id=None, recipient_name=name)
    await state.set_state(SendMail.choosing_date)
    await message.answer(SEND_DATE, reply_markup=date_keyboard())


@router.callback_query(SendMail.choosing_date, F.data == DATE_TODAY)
async def choose_today(callback: CallbackQuery, state: FSMContext) -> None:
    message = callback_message(callback)
    if message is None:
        await callback.answer(SEND_EXPIRED, show_alert=True)
        return
    await callback.answer()
    await state.update_data(sent_at=date.today().isoformat())
    await message.edit_reply_markup(reply_markup=None)
    await show_confirmation(message, state)


@router.callback_query(SendMail.choosing_date, F.data == DATE_OTHER)
async def request_custom_date(callback: CallbackQuery, state: FSMContext) -> None:
    message = callback_message(callback)
    if message is None:
        await callback.answer(SEND_EXPIRED, show_alert=True)
        return
    await callback.answer()
    await state.set_state(SendMail.entering_date)
    await message.edit_text(SEND_DATE_CUSTOM)


@router.message(SendMail.entering_date, F.text)
async def accept_custom_date(message: Message, state: FSMContext) -> None:
    sent_at = parse_sent_date(message.text or "")
    if sent_at is None:
        await message.answer(SEND_DATE_INVALID)
        return

    await state.update_data(sent_at=sent_at.isoformat())
    await show_confirmation(message, state)


@router.callback_query(SendMail.confirming, F.data == CHANGE_RECIPIENT)
async def change_recipient(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    message = callback_message(callback)
    if message is None:
        await callback.answer(SEND_EXPIRED, show_alert=True)
        return
    try:
        owner_id = int((await state.get_data())["owner_id"])
    except KeyError, TypeError, ValueError:
        await callback.answer(SEND_EXPIRED, show_alert=True)
        return

    correspondents = await Correspondent.for_owner(session, owner_id)
    await callback.answer()
    await state.update_data(correspondent_id=None, recipient_name=None)
    await state.set_state(SendMail.choosing_recipient)
    await message.edit_text(SEND_RECIPIENT, reply_markup=recipient_keyboard(correspondents))


@router.callback_query(SendMail.confirming, F.data == CHANGE_DATE)
async def change_date(callback: CallbackQuery, state: FSMContext) -> None:
    message = callback_message(callback)
    if message is None:
        await callback.answer(SEND_EXPIRED, show_alert=True)
        return
    await callback.answer()
    await state.set_state(SendMail.choosing_date)
    await message.edit_text(SEND_DATE, reply_markup=date_keyboard())


@router.callback_query(SendMail.confirming, F.data == CONFIRM_SEND)
async def confirm_send(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    message = callback_message(callback)
    if message is None:
        await callback.answer(SEND_EXPIRED, show_alert=True)
        return

    data = await state.get_data()
    try:
        owner_id = int(data["owner_id"])
        recipient_name = str(data["recipient_name"])
        sent_at = date.fromisoformat(str(data["sent_at"]))
    except KeyError, TypeError, ValueError:
        await callback.answer(SEND_EXPIRED, show_alert=True)
        await state.clear()
        return

    correspondent_id = data.get("correspondent_id")
    correspondent: Correspondent | None
    if correspondent_id is None:
        correspondent = await Correspondent.find_or_create(
            session,
            owner_id=owner_id,
            name=recipient_name,
        )
    else:
        correspondent = await Correspondent.find_for_owner(
            session,
            owner_id=owner_id,
            correspondent_id=int(correspondent_id),
        )
        if correspondent is None:
            await callback.answer(SEND_EXPIRED, show_alert=True)
            await state.clear()
            return

    await MailItem.create(
        session,
        owner_id=owner_id,
        correspondent_id=correspondent.id,
        direction=MailDirection.OUTGOING,
        sent_at=sent_at,
    )
    await state.clear()
    await callback.answer()
    await message.edit_text(
        f"{SEND_SAVED}\n\n"
        f"Кому: <b>{escape(correspondent.name)}</b>\n"
        f"Отправлено: <b>{format_date(sent_at)}</b>\n"
        "Статус: <b>в пути</b>"
    )
    await message.answer("Что будем делать?", reply_markup=main_menu_keyboard())


@router.callback_query(F.data == CANCEL_SEND)
async def cancel_send(callback: CallbackQuery, state: FSMContext) -> None:
    message = callback_message(callback)
    await state.clear()
    if message is None:
        await callback.answer(SEND_CANCELLED, show_alert=True)
        return
    await callback.answer()
    await message.edit_text(SEND_CANCELLED)
    await message.answer("Что будем делать?", reply_markup=main_menu_keyboard())


@router.message(StateFilter(SendMail))
async def request_send_action(message: Message) -> None:
    await message.answer(SEND_USE_BUTTONS, reply_markup=ReplyKeyboardRemove())
