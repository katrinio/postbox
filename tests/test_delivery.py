import asyncio
from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from postbox.handlers.delivery import delivery_confirmation_text, parse_delivery_date, parse_mark_callback
from postbox.keyboards.delivery import mark_received_callback
from postbox.models import (
    Correspondent,
    MailDeliveryError,
    MailDirection,
    MailItem,
    MailJournalFilter,
    MailStatus,
)


def make_mail(
    *,
    direction: MailDirection = MailDirection.OUTGOING,
    sent_at: date | None = None,
    received_at: date | None = None,
) -> MailItem:
    correspondent = Correspondent(id=2, owner_id=1, name="Masha <3")
    return MailItem(
        id=3,
        owner_id=1,
        correspondent_id=2,
        correspondent=correspondent,
        direction=direction,
        sent_at=sent_at,
        received_at=received_at,
    )


def test_mark_callback_round_trip() -> None:
    callback = mark_received_callback(42, MailJournalFilter.IN_TRANSIT, 3)

    assert parse_mark_callback(callback) == (42, MailJournalFilter.IN_TRANSIT, 3)
    assert parse_mark_callback("broken") is None
    assert parse_mark_callback("delivery:mark:42:unknown:3") is None


def test_delivery_date_must_fit_the_mail_journey() -> None:
    sent_at = date(2026, 7, 10)
    today = date(2026, 7, 16)

    assert parse_delivery_date("15.07.2026", sent_at=sent_at, today=today) == date(2026, 7, 15)
    assert parse_delivery_date("09.07.2026", sent_at=sent_at, today=today) is None
    assert parse_delivery_date("17.07.2026", sent_at=sent_at, today=today) is None
    assert parse_delivery_date("not a date", sent_at=sent_at, today=today) is None


def test_delivery_confirmation_shows_escaped_recipient_and_travel_time() -> None:
    mail = make_mail(sent_at=date(2026, 7, 10))

    text = delivery_confirmation_text(mail, date(2026, 7, 15))

    assert "Кому: <b>Masha &lt;3</b>" in text
    assert "Получено: <b>15.07.2026</b>" in text
    assert "Путешествие: <b>5 дн.</b>" in text


def test_active_record_marks_outgoing_mail_as_received() -> None:
    today = date.today()
    mail = make_mail(sent_at=today - timedelta(days=4))
    session = AsyncMock(spec=AsyncSession)

    with patch.object(MailItem, "save", new=AsyncMock(return_value=mail)) as save:
        result = asyncio.run(mail.mark_received(session, received_at=today))

    assert result is mail
    assert mail.received_at == today
    assert mail.status is MailStatus.RECEIVED
    assert mail.travel_days() == 4
    save.assert_awaited_once_with(session)


@pytest.mark.parametrize(
    ("mail", "received_at"),
    [
        (make_mail(direction=MailDirection.INCOMING, received_at=date.today()), date.today()),
        (make_mail(sent_at=date.today() - timedelta(days=2), received_at=date.today()), date.today()),
        (make_mail(sent_at=date.today()), date.today() - timedelta(days=1)),
        (make_mail(sent_at=date.today()), date.today() + timedelta(days=1)),
    ],
)
def test_active_record_rejects_invalid_delivery_transition(mail: MailItem, received_at: date) -> None:
    session = AsyncMock(spec=AsyncSession)

    with pytest.raises(MailDeliveryError):
        asyncio.run(mail.mark_received(session, received_at=received_at))
