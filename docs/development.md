# Development

## Setup

- Python 3.14
- Poetry 2
- PostgreSQL 17+

```bash
poetry install
```

Create a bot with [BotFather](https://t.me/BotFather), copy the example settings,
and put the token in the local `.env` file:

```bash
cp .env.example .env
```

Postbox loads `.env` from the current working directory. Existing process
environment variables take priority over values from the file.

`POSTBOX_LOG_LEVEL` is optional and defaults to `INFO`.

For the local web API, set `POSTBOX_WEB_OWNER_TELEGRAM_ID` to the Telegram ID
of the journal owner. This is a temporary local-only owner selection until web
authentication is implemented.

Create the schema before the first run and after pulling new migrations:

```bash
poetry run alembic upgrade head
```

## Run

```bash
poetry run postbox
```

## Checks

```bash
poetry run ruff check .
poetry run mypy src
poetry run pytest
```

Database integration tests run when `POSTBOX_TEST_DATABASE_URL` is set. CI runs
them against an isolated PostgreSQL service.

## Web application

The server-rendered web interface is built into the Python package (FastAPI + Jinja2).
Start the application:

```bash
poetry run postbox-api
```

Open <http://localhost:8000/login>.
