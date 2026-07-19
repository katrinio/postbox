# Postbox web

Mobile-first interface for the Postbox PWA.

The Journal screen reads real mail records from the local Python API. The Home and New screens still use
demonstration content while their workflows are being built.

## Requirements

- Node.js 22.13 or newer

The repository pins Node.js 22 in `.node-version` and `.nvmrc`. With Homebrew on Apple Silicon, enable it in the
current terminal before running npm commands:

```bash
export PATH="/opt/homebrew/opt/node@22/bin:$PATH"
```

## Development

Set `POSTBOX_WEB_OWNER_TELEGRAM_ID` in the repository-level `.env`, then start the API from the repository root:

```bash
poetry run postbox-api
```

Start the interface in a second terminal:

```bash
npm install
npm run dev
```

Open <http://localhost:3000>.

The interface uses <http://localhost:8000> by default. Set `NEXT_PUBLIC_POSTBOX_API_URL` when the API is available
at another address.

The settings button in the header switches the Home screen between normal, empty, and offline preview
states.

## Validation

```bash
npm run build
npm run lint
```
