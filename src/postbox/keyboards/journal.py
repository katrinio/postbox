# ruff: noqa: RUF001

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from postbox.handlers.common import format_date
from postbox.keyboards.delivery import mark_received_callback
from postbox.models import MailDirection, MailItem, MailJournalFilter, MailJournalPage, MailJournalStats

FILTERS_CALLBACK = "journal:filters"
LIST_PREFIX = "journal:list:"
ITEM_PREFIX = "journal:item:"
NOOP_CALLBACK = "journal:noop"


def list_callback(view: MailJournalFilter, page: int) -> str:
    return f"{LIST_PREFIX}{view.value}:{page}"


def item_callback(mail_id: int, view: MailJournalFilter, page: int) -> str:
    return f"{ITEM_PREFIX}{mail_id}:{view.value}:{page}"


def journal_filters_keyboard(stats: MailJournalStats) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"🕊 В пути · {stats.in_transit}",
                    callback_data=list_callback(MailJournalFilter.IN_TRANSIT, 1),
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"📮 Исходящие · {stats.outgoing}",
                    callback_data=list_callback(MailJournalFilter.OUTGOING, 1),
                ),
                InlineKeyboardButton(
                    text=f"📬 Входящие · {stats.incoming}",
                    callback_data=list_callback(MailJournalFilter.INCOMING, 1),
                ),
            ],
            [
                InlineKeyboardButton(
                    text=f"Все письма · {stats.total}",
                    callback_data=list_callback(MailJournalFilter.ALL, 1),
                )
            ],
        ]
    )


def journal_entry_label(mail: MailItem) -> str:
    name = mail.correspondent.name
    if len(name) > 18:
        name = f"{name[:17]}…"
    if mail.direction is MailDirection.INCOMING:
        return f"← {name} · {format_date(mail.journal_date)} · получено"
    status = "в пути" if mail.received_at is None else "дошло"
    return f"→ {name} · {format_date(mail.journal_date)} · {status}"


def journal_list_keyboard(page: MailJournalPage) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=journal_entry_label(mail),
                callback_data=item_callback(mail.id, page.view, page.page),
            )
        ]
        for mail in page.items
    ]
    if page.pages > 1:
        pagination = []
        if page.page > 1:
            pagination.append(InlineKeyboardButton(text="←", callback_data=list_callback(page.view, page.page - 1)))
        pagination.append(InlineKeyboardButton(text=f"{page.page}/{page.pages}", callback_data=NOOP_CALLBACK))
        if page.page < page.pages:
            pagination.append(InlineKeyboardButton(text="→", callback_data=list_callback(page.view, page.page + 1)))
        rows.append(pagination)
    rows.append([InlineKeyboardButton(text="К разделам", callback_data=FILTERS_CALLBACK)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def journal_detail_keyboard(mail: MailItem, view: MailJournalFilter, page: int) -> InlineKeyboardMarkup:
    rows = []
    if mail.direction is MailDirection.OUTGOING and mail.received_at is None:
        rows.append(
            [
                InlineKeyboardButton(
                    text="✓ Письмо дошло",
                    callback_data=mark_received_callback(mail.id, view, page),
                )
            ]
        )
    rows.extend(
        [
            [InlineKeyboardButton(text="← К списку", callback_data=list_callback(view, page))],
            [InlineKeyboardButton(text="К разделам", callback_data=FILTERS_CALLBACK)],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)
