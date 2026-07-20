# Storage

Postbox stores each user's private mail journal in PostgreSQL. The bot process
does not keep durable state on its local filesystem.

## Records

- `users` identifies journal owners by their Telegram ID.
- `correspondents` is a private address book scoped to one user.
- `mail_items` stores incoming and outgoing paper mail.

Mail status is derived from `received_at`; it is not stored separately.
Outgoing mail always has a sent date. Incoming mail always has a received date,
while its sent date may remain unknown when the postmark cannot be read.

## Isolation

Every correspondent and mail item belongs to a user. A composite foreign key
prevents a mail item from referring to another user's correspondent.

## Connection

`POSTBOX_DATABASE_URL` contains the database connection URL. Both SQLite and
PostgreSQL are supported and both require an async driver: use
`sqlite+aiosqlite://` for SQLite or `postgresql+psycopg://` for PostgreSQL. A
synchronous `sqlite://` URL is rejected at startup with a configuration error.
For PostgreSQL, production should use a dedicated database and role with only the
permissions Postbox needs.

## Migrations and backups

Alembic owns schema changes. Run `poetry run alembic upgrade head` during a
release, before restarting the bot. PostgreSQL backups are managed outside the
application and should be tested by restoring them into a separate database.
