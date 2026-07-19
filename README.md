# postbox

A multi-user web journal for paper letters and postcards with Telegram authentication.

---

<div align="center">
  <img src="docs/images/postbox.png" width="500"/>
</div>

---

Some letters arrive.

Some disappear.

All are remembered.

## Goal

Keep track of outgoing and incoming paper mail.

Record when a letter was sent, when it arrived (if it did), and how long the journey took.

## Status

- ✅ Multi-user web app with Telegram Login authentication
- ✅ Auto-approval for first 5 users (configurable limit)
- ✅ JWT-based sessions and data isolation per user
- ✅ PostgreSQL storage with Alembic migrations
- ✅ FastAPI backend with JSON REST API
- 🚀 Mobile-first PWA (Next.js) without app stores

## Documentation

- [MVP](docs/mvp.md)

- [Roadmap](docs/roadmap.md)

- [Visual direction](docs/design.md)

## Tech stack

**Backend:** `Python` · `FastAPI` · `SQLAlchemy` · `Alembic` · `PostgreSQL` · `JWT` · `Telegram Login`

**Frontend:** `React` · `Next.js` · `TypeScript`
