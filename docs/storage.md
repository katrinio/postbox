# Storage

Postbox stores each user's private mail journal in SQLite. Production uses a
single file database mounted at `/data/postbox.db` inside the Docker container.

## Records

- `users` identifies journal owners by their Telegram ID.
- `correspondents` is a private address book scoped to one user.
- `mail_items` stores incoming and outgoing paper mail.

Correspondents answer "who"; mail item geography answers "where this specific
letter travelled." A single correspondent can send from, or receive mail in,
different places over time, so origin and destination live on `mail_items`.
Country values are stored as optional ISO 3166-1 alpha-2 codes such as `DE`,
`FR`, `IT`, or `CZ`. City values are optional free text.

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

## Schema and backups

Tables are auto-created at startup via `Base.metadata.create_all`. Alembic
migrations are available for schema changes (`poetry run alembic upgrade head`).

SQLite backups use atomic `VACUUM INTO` via `scripts/backup_sqlite.sh`.
See [deployment guide](deployment.md) for backup schedule and restore procedure.
