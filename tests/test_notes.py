import asyncio
from datetime import date
from unittest.mock import AsyncMock, patch

import pytest
from postbox.handlers.notes import note_confirmation_text, parse_note_callback
from postbox.keyboards.notes import DELETE_NOTE_PREFIX, EDIT_NOTE_PREFIX, delete_note_callback, edit_note_callback
from sqlalchemy.ext.asyncio import AsyncSession

from postbox.models import Correspondent, MailDirection, MailItem, MailJournalFilter, MailNoteError


def make_mail(*, note: str | None = None) -> MailItem:
    correspondent = Correspondent(id=2, owner_id=1, name="Masha")
    return MailItem(
        id=3,
        owner_id=1,
        correspondent_id=2,
        correspondent=correspondent,
        direction=MailDirection.OUTGOING,
        sent_at=date(2026, 7, 15),
        received_at=None,
        note=note,
    )


def test_note_callbacks_round_trip() -> None:
    edit = edit_note_callback(42, MailJournalFilter.OUTGOING, 2)
    delete = delete_note_callback(42, MailJournalFilter.ALL, 3)

    assert parse_note_callback(edit, EDIT_NOTE_PREFIX) == (42, MailJournalFilter.OUTGOING, 2)
    assert parse_note_callback(delete, DELETE_NOTE_PREFIX) == (42, MailJournalFilter.ALL, 3)
    assert parse_note_callback(edit, DELETE_NOTE_PREFIX) is None
    assert parse_note_callback("broken", EDIT_NOTE_PREFIX) is None


def test_note_confirmation_escapes_telegram_html() -> None:
    text = note_confirmation_text("Редкая <открытка> & письмо")

    assert "Редкая &lt;открытка&gt; &amp; письмо" in text


def test_active_record_sets_and_removes_normalized_note() -> None:
    mail = make_mail()
    session = AsyncMock(spec=AsyncSession)

    with patch.object(MailItem, "save", new=AsyncMock(return_value=mail)) as save:
        asyncio.run(mail.set_note(session, note="  Первая строка\nВторая строка  "))
        assert mail.note == "Первая строка\nВторая строка"

        asyncio.run(mail.set_note(session, note=None))
        assert mail.note is None

    assert save.await_count == 2


@pytest.mark.parametrize("note", ["", "   ", "x" * 1001])
def test_active_record_rejects_invalid_note(note: str) -> None:
    mail = make_mail()
    session = AsyncMock(spec=AsyncSession)

    with pytest.raises(MailNoteError):
        asyncio.run(mail.set_note(session, note=note))
