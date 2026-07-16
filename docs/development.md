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

The mobile interface lives in `web/` and requires Node.js 22.13 or newer. The
version is pinned in `web/.node-version` and `web/.nvmrc`. Start the read-only
journal API from the repository root:

```bash
poetry run postbox-api
```

Then start the interface in a second terminal:

```bash
cd web
npm install
npm run dev
```

Open <http://localhost:3000>. The Journal screen reads real records from
PostgreSQL through <http://localhost:8000>. The Home and New screens remain
visual prototypes for now. The settings button switches the Home screen between
normal, empty, and offline preview states.

Frontend checks:

```bash
npm run lint
npm test
```
