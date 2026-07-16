from postbox.models.correspondent import Correspondent
from postbox.models.mail_item import (
    MAX_NOTE_LENGTH,
    MailDeliveryError,
    MailDirection,
    MailItem,
    MailJournalFilter,
    MailJournalPage,
    MailJournalStats,
    MailNoteError,
    MailStatus,
)
from postbox.models.user import User

__all__ = [
    "MAX_NOTE_LENGTH",
    "Correspondent",
    "MailDeliveryError",
    "MailDirection",
    "MailItem",
    "MailJournalFilter",
    "MailJournalPage",
    "MailJournalStats",
    "MailNoteError",
    "MailStatus",
    "User",
]
