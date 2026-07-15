# Development

## Setup

- Python 3.14
- Poetry 2

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
