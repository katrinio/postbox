from datetime import date
from html import escape

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from postbox.handlers.common import callback_message, format_date, owner_by_telegram_id, parse_date
from postbox.handlers.journal import journal_detail_text
from postbox.keyboards.delivery import (
    CANCEL_DELIVERY,
    CHANGE_DELIVERY_DATE,
    CONFIRM_DELIVERY,
    DELIVERY_OTHER,
    DELIVERY_TODAY,
    MARK_RECEIVED_PREFIX,
    delivery_confirmation_keyboard,
    delivery_date_keyboard,
)
from postbox.keyboards.journal import journal_detail_keyboard
from postbox.models import MailDeliveryError, MailDirection, MailItem, MailJournalFilter
from postbox.texts import (
    DELIVERY_DATE,
    DELIVERY_DATE_CUSTOM,
    DELIVERY_DATE_INVALID,
    DELIVERY_EXPIRED,
    DELIVERY_USE_BUTTONS,
)

router = Router(name=__name__)


class MarkDelivery(StatesGroup):
    choosing_date = State()
    entering_date = State()
    confirming = State()


def parse_mark_callback(data: str) -> tuple[int, MailJournalFilter, int] | None:
    try:
        prefix, mail_id, view_value, page_value = data.rsplit(":", 3)
        if f"{prefix}:" != MARK_RECEIVED_PREFIX:
            return None
        return int(mail_id), MailJournalFilter(view_value), int(page_value)
    except ValueError:
        return None


def parse_delivery_date(
    value: str,
    *,
    sent_at: date,
    today: date | None = None,
) -> date | None:
    parsed = parse_date(value, latest=today)
    if parsed is None or parsed < sent_at:
        return None
    return parsed


def delivery_confirmation_text(mail: MailItem, received_at: date) -> str:
    if mail.sent_at is None:
        raise MailDeliveryError("outgoing mail has no sent date")
    days = (received_at - mail.sent_at).days
    return (
        "Проверим доставку:\n\n"
        f"Кому: <b>{escape(mail.correspondent.name)}</b>\n"
        f"Отправлено: <b>{format_date(mail.sent_at)}</b>\n"
        f"Получено: <b>{format_date(received_at)}</b>\n"
        f"Путешествие: <b>{days} дн.</b>"
    )


async def load_delivery_mail(
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
    if mail is None or mail.direction is not MailDirection.OUTGOING or mail.received_at is not None:
        return None
    return mail, view, page


async def show_confirmation(message: Message, state: FSMContext, mail: MailItem, received_at: date) -> None:
    await state.update_data(received_at=received_at.isoformat())
    await state.set_state(MarkDelivery.confirming)
    await message.answer(
        delivery_confirmation_text(mail, received_at),
        reply_markup=delivery_confirmation_keyboard(),
    )


@router.callback_query(F.data.startswith(MARK_RECEIVED_PREFIX))
async def begin_mark_received(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    message = callback_message(callback)
    parsed = parse_mark_callback(callback.data or "")
    owner = await owner_by_telegram_id(session, callback.from_user.id)
    if message is None or parsed is None or owner is None:
        await callback.answer(DELIVERY_EXPIRED, show_alert=True)
        return

    mail_id, view, page = parsed
    mail = await MailItem.find_for_owner(session, owner_id=owner.id, mail_id=mail_id)
    if mail is None or mail.direction is not MailDirection.OUTGOING or mail.received_at is not None:
        await callback.answer(DELIVERY_EXPIRED, show_alert=True)
        return

    await state.clear()
    await state.update_data(mail_id=mail.id, view=view.value, page=page)
    await state.set_state(MarkDelivery.choosing_date)
    await callback.answer()
    await message.edit_text(DELIVERY_DATE, reply_markup=delivery_date_keyboard())


@router.callback_query(MarkDelivery.choosing_date, F.data == DELIVERY_TODAY)
async def delivery_today(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    message = callback_message(callback)
    loaded = await load_delivery_mail(callback.from_user.id, state, session)
    if message is None or loaded is None:
        await callback.answer(DELIVERY_EXPIRED, show_alert=True)
        await state.clear()
        return
    mail, _, _ = loaded
    await callback.answer()
    await message.edit_reply_markup(reply_markup=None)
    await show_confirmation(message, state, mail, date.today())


@router.callback_query(MarkDelivery.choosing_date, F.data == DELIVERY_OTHER)
async def request_delivery_date(callback: CallbackQuery, state: FSMContext) -> None:
    message = callback_message(callback)
    if message is None:
        await callback.answer(DELIVERY_EXPIRED, show_alert=True)
        return
    await callback.answer()
    await state.set_state(MarkDelivery.entering_date)
    await message.edit_text(DELIVERY_DATE_CUSTOM)


@router.message(MarkDelivery.entering_date, F.text)
async def accept_delivery_date(message: Message, state: FSMContext, session: AsyncSession) -> None:
    telegram_user = message.from_user
    if telegram_user is None:
        await state.clear()
        await message.answer(DELIVERY_EXPIRED)
        return
    loaded = await load_delivery_mail(telegram_user.id, state, session)
    if loaded is None:
        await state.clear()
        await message.answer(DELIVERY_EXPIRED)
        return
    mail, _, _ = loaded
    if mail.sent_at is None:
        await state.clear()
        await message.answer(DELIVERY_EXPIRED)
        return
    received_at = parse_delivery_date(message.text or "", sent_at=mail.sent_at)
    if received_at is None:
        await message.answer(DELIVERY_DATE_INVALID)
        return
    await show_confirmation(message, state, mail, received_at)


@router.callback_query(MarkDelivery.confirming, F.data == CHANGE_DELIVERY_DATE)
async def change_delivery_date(callback: CallbackQuery, state: FSMContext) -> None:
    message = callback_message(callback)
    if message is None:
        await callback.answer(DELIVERY_EXPIRED, show_alert=True)
        return
    await state.update_data(received_at=None)
    await state.set_state(MarkDelivery.choosing_date)
    await callback.answer()
    await message.edit_text(DELIVERY_DATE, reply_markup=delivery_date_keyboard())


@router.callback_query(MarkDelivery.confirming, F.data == CONFIRM_DELIVERY)
async def confirm_delivery(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    message = callback_message(callback)
    loaded = await load_delivery_mail(callback.from_user.id, state, session)
    data = await state.get_data()
    if message is None or loaded is None:
        await callback.answer(DELIVERY_EXPIRED, show_alert=True)
        await state.clear()
        return
    try:
        received_at = date.fromisoformat(str(data["received_at"]))
    except KeyError, ValueError:
        await callback.answer(DELIVERY_EXPIRED, show_alert=True)
        await state.clear()
        return

    mail, view, page = loaded
    try:
        await mail.mark_received(session, received_at=received_at)
    except MailDeliveryError:
        await callback.answer(DELIVERY_EXPIRED, show_alert=True)
        await state.clear()
        return

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
    loaded = await load_delivery_mail(telegram_id, state, session)
    if loaded is None:
        return None
    mail, view, page = loaded
    return journal_detail_text(mail), journal_detail_keyboard(mail, view, page)


@router.callback_query(F.data == CANCEL_DELIVERY)
async def cancel_delivery(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    message = callback_message(callback)
    restored = await restore_mail_detail(callback.from_user.id, state, session)
    await state.clear()
    if message is None or restored is None:
        await callback.answer(DELIVERY_EXPIRED, show_alert=True)
        return
    text, keyboard = restored
    await callback.answer()
    await message.edit_text(text, reply_markup=keyboard)


@router.message(StateFilter(MarkDelivery), Command("cancel"))
async def cancel_delivery_command(message: Message, state: FSMContext, session: AsyncSession) -> None:
    telegram_user = message.from_user
    restored = None if telegram_user is None else await restore_mail_detail(telegram_user.id, state, session)
    await state.clear()
    if restored is None:
        await message.answer(DELIVERY_EXPIRED)
        return
    text, keyboard = restored
    await message.answer(text, reply_markup=keyboard)


@router.message(StateFilter(MarkDelivery))
async def request_delivery_action(message: Message) -> None:
    await message.answer(DELIVERY_USE_BUTTONS)
