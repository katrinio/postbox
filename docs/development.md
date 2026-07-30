# Development

## Setup

- Python 3.14
- Poetry 2
- PostgreSQL 17+

```bash
poetry install
```

Copy the example settings and fill in the local `.env` file:

```bash
cp .env.example .env
```

Postbox loads `.env` from the current working directory. Existing process
environment variables take priority over values from the file.

Postbox login goes through The Hub Bot. Set `HUB_AUTH_SECRET` to the shared
secret used by The Hub, and set `HUB_BOT_URL` to the ready-to-open Hub Bot link
for Postbox, for example `https://t.me/<hub-bot>?start=postbox`.

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
