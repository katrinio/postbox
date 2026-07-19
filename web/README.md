# Postbox web

Mobile-first interface for the Postbox PWA with multi-user support and Telegram authentication.

## Features

- **Telegram Login** — Authenticate via Telegram Login Widget
- **Multi-user support** — Up to 5 users can register (configurable limit)
- **Auto-approval** — First 5 users are automatically approved
- **Journal screen** — Real-time access to mail records from Python API
- **Light/Dark themes** — System, light, or dark mode

## Requirements

- Node.js 22.13 or newer

The repository pins Node.js 22 in `.node-version` and `.nvmrc`. With Homebrew on Apple Silicon, enable it in the
current terminal before running npm commands:

```bash
export PATH="/opt/homebrew/opt/node@22/bin:$PATH"
```

## Development

Set required environment variables in the repository-level `.env`:

```bash
POSTBOX_DATABASE_URL=postgresql+psycopg://postbox:postbox@127.0.0.1:55432/postbox
POSTBOX_JWT_SECRET_KEY=your-secret-key-here
POSTBOX_REGISTRATION_LIMIT=5
```

Start the API from the repository root:

```bash
poetry run postbox-api
```

Start the interface in a second terminal:

```bash
npm install
npm run dev
```

Open <http://localhost:3000>. You'll be redirected to `/login` to authenticate via Telegram.

The interface uses `http://localhost:8000` by default. Set `NEXT_PUBLIC_POSTBOX_API_URL` when the API is available
at another address.

## Authentication

The app requires Telegram Login Widget authentication. Users are auto-approved if the user limit (default 5) is not reached.
After approval, users receive a JWT token stored in localStorage.

## Validation

```bash
npm run build
npm run lint
```
