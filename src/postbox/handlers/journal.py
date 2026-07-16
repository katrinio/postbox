# ruff: noqa: RUF001

from datetime import date
from html import escape

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from postbox.handlers.common import callback_message, format_date, register_owner
from postbox.keyboards.journal import (
    FILTERS_CALLBACK,
    ITEM_PREFIX,
    LIST_PREFIX,
    NOOP_CALLBACK,
    journal_detail_keyboard,
    journal_filters_keyboard,
    journal_list_keyboard,
)
from postbox.keyboards.main_menu import MainMenuAction, main_menu_keyboard
from postbox.models import MailDirection, MailItem, MailJournalFilter, MailJournalPage, User
from postbox.texts import JOURNAL_EMPTY, JOURNAL_EXPIRED, JOURNAL_TITLE

router = Router(name=__name__)

VIEW_TITLES = {
    MailJournalFilter.ALL: "Все письма",
    MailJournalFilter.IN_TRANSIT: "В пути",
    MailJournalFilter.OUTGOING: "Исходящие",
    MailJournalFilter.INCOMING: "Входящие",
}


def journal_list_text(page: MailJournalPage) -> str:
    title = VIEW_TITLES[page.view]
    if not page.items:
        return f"<b>{title}</b>\n\n{JOURNAL_EMPTY}"
    return f"<b>{title}</b>\n\nНайдено записей: {page.total}"


def journal_detail_text(mail: MailItem, *, today: date | None = None) -> str:
    name = escape(mail.correspondent.name)
    sent = format_date(mail.sent_at) if mail.sent_at is not None else "неизвестно"
    received = format_date(mail.received_at) if mail.received_at is not None else "—"
    travel_days = mail.travel_days(today=today)

    if mail.direction is MailDirection.OUTGOING:
        title = "Исходящее письмо"
        person = f"Кому: <b>{name}</b>"
        status = "в пути" if mail.received_at is None else "дошло"
    else:
        title = "Входящее письмо"
        person = f"От кого: <b>{name}</b>"
        status = "получено"

    lines = [
        f"<b>{title}</b>",
        "",
        person,
        f"Отправлено: <b>{sent}</b>",
        f"Получено: <b>{received}</b>",
        f"Статус: <b>{status}</b>",
    ]
    if travel_days is not None:
        label = "В пути" if mail.received_at is None else "Путешествие"
        lines.append(f"{label}: <b>{travel_days} дн.</b>")
    return "\n".join(lines)


def parse_list_callback(data: str) -> tuple[MailJournalFilter, int] | None:
    try:
        prefix, view_value, page_value = data.rsplit(":", 2)
        if f"{prefix}:" != LIST_PREFIX:
            return None
        return MailJournalFilter(view_value), int(page_value)
    except ValueError:
        return None


def parse_item_callback(data: str) -> tuple[int, MailJournalFilter, int] | None:
    try:
        prefix, mail_id, view_value, page_value = data.rsplit(":", 3)
        if f"{prefix}:" != ITEM_PREFIX:
            return None
        return int(mail_id), MailJournalFilter(view_value), int(page_value)
    except ValueError:
        return None


async def callback_owner(callback: CallbackQuery, session: AsyncSession) -> User | None:
    return await User.find_by_telegram_id(session, callback.from_user.id)


async def answer_expired(callback: CallbackQuery) -> None:
    await callback.answer(JOURNAL_EXPIRED, show_alert=True)


@router.message(F.text == MainMenuAction.JOURNAL)
async def begin_journal(message: Message, session: AsyncSession) -> None:
    owner = await register_owner(message, session)
    if owner is None:
        await message.answer(JOURNAL_EXPIRED, reply_markup=main_menu_keyboard())
        return
    stats = await MailItem.journal_stats(session, owner.id)
    await message.answer(JOURNAL_TITLE, reply_markup=journal_filters_keyboard(stats))


@router.callback_query(F.data == FILTERS_CALLBACK)
async def show_journal_filters(callback: CallbackQuery, session: AsyncSession) -> None:
    message = callback_message(callback)
    owner = await callback_owner(callback, session)
    if message is None or owner is None:
        await answer_expired(callback)
        return
    stats = await MailItem.journal_stats(session, owner.id)
    await callback.answer()
    await message.edit_text(JOURNAL_TITLE, reply_markup=journal_filters_keyboard(stats))


@router.callback_query(F.data.startswith(LIST_PREFIX))
async def show_journal_list(callback: CallbackQuery, session: AsyncSession) -> None:
    message = callback_message(callback)
    parsed = parse_list_callback(callback.data or "")
    owner = await callback_owner(callback, session)
    if message is None or parsed is None or owner is None:
        await answer_expired(callback)
        return

    view, page_number = parsed
    page = await MailItem.journal_page(
        session,
        owner.id,
        view=view,
        page=page_number,
    )
    await callback.answer()
    await message.edit_text(journal_list_text(page), reply_markup=journal_list_keyboard(page))


@router.callback_query(F.data.startswith(ITEM_PREFIX))
async def show_mail_detail(callback: CallbackQuery, session: AsyncSession) -> None:
    message = callback_message(callback)
    parsed = parse_item_callback(callback.data or "")
    owner = await callback_owner(callback, session)
    if message is None or parsed is None or owner is None:
        await answer_expired(callback)
        return

    mail_id, view, page = parsed
    mail = await MailItem.find_for_owner(
        session,
        owner_id=owner.id,
        mail_id=mail_id,
    )
    if mail is None:
        await answer_expired(callback)
        return

    await callback.answer()
    await message.edit_text(
        journal_detail_text(mail),
        reply_markup=journal_detail_keyboard(view, page),
    )


@router.callback_query(F.data == NOOP_CALLBACK)
async def ignore_page_number(callback: CallbackQuery) -> None:
    await callback.answer()
