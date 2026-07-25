# Server-Render Migration Plan

> **Status:** planning only. No migration performed. No Docker/frontend/deployment changes. Source of truth for later implementation sessions.
>
> **Decisions locked (see §13):**
> - **D1 — Telegram auth:** target a **normal browser website** using the **Telegram Login Widget** (server-side verification of Telegram-signed data → existing Postbox JWT → **HttpOnly, Secure, SameSite=Lax cookie** → POST → 303 → GET). No `localStorage`, JWT never exposed to JS. No server-side sessions unless a concrete need appears. Keep the existing JWT create/decode. The currently-disabled signature verification is a **security bug** whose fix gates completion of the auth phase.
> - **D2 — no new features:** migrate **only** what genuinely works today (login, journal read/list, health/readiness, required nav/layout). Mocked / modeled-but-unexposed / incomplete flows stay **out of scope**. Do **not** build create/edit/mark-received/note forms just because the models exist. Reach parity first; evaluate features separately afterward.
>
> **D1 mechanism finding (verified in code):** the backend already implements the **Login Widget** algorithm (`auth.py`: `secret_key = SHA256(bot_token)`) and a **flat Login-Widget DTO** (`TelegramLoginRequest`). The **WebApp/Mini-App** scheme (`HMAC(bot_token,"WebAppData")`) is **not** implemented. Only the *frontend* (`telegram-web-app.ts`, being deleted) read `window.Telegram.WebApp.initData`. So moving to the Login Widget **aligns with the existing backend** — no crypto rewrite; wire the real `POSTBOX_BOT_TOKEN`, remove the `dev_hash_*` bypass, and take data from the widget's signed redirect. **Do not mix Login Widget and WebApp initData validation.**

Goal: collapse the current split (FastAPI backend + vinext/Node frontend, two ports, nginx routing, JWT-in-localStorage) into one conventional server-rendered Python app:

```
Browser → nginx → uvicorn/Postbox (:8000)
                    ├── FastAPI routes → Jinja2 templates
                    ├── /static (CSS, minimal JS, fonts, icons)
                    ├── business logic (existing model methods)
                    └── SQLite (existing SQLAlchemy + Alembic)
```

One runtime, one process, one port, one healthcheck, one artifact. No Node/npm/vinext in production.

---

## 1. Current architecture summary

Backend (`src/postbox/`, ~1.5k LOC):

- `api.py` — FastAPI app factory (`create_app`), 4 routes, CORS, `run()` (uvicorn).
- `auth.py` — Telegram HMAC check + JWT encode/decode + auth DTOs.
- `config.py` — `WebSettings` (web app) and `Settings` (bot, unused by the app today).
- `models/` — `User`, `Correspondent`, `MailItem` as ActiveRecord classes holding **all business logic**.
- `database/` — async engine + session factory (`connection.py`), declarative base + `ActiveRecord` (`base.py`).
- `logging.py` — logging config.
- `migrations/` — Alembic (PostgreSQL path); SQLite production creates schema via `Base.metadata.create_all` at startup (`api.py`).

Frontend (`web/`, vinext = Next.js for Cloudflare Workers):

- `app/page.tsx` — client component: Home (mock), Journal (real fetch), New (mock), tabs, theme, preview sheet.
- `app/JournalScreen.tsx` — journal fetch + render (the only real data screen).
- `app/login/page.tsx` — Telegram WebApp auth + dev login form.
- `app/hooks/useAuth.ts`, `app/lib/telegram-web-app.ts` — token/localStorage + Telegram WebApp helpers.
- `app/globals.css` (799 lines) — full design-token system, framework-agnostic CSS.
- `worker/index.ts`, `vite.config.ts`, `next.config.ts` — Cloudflare Worker/vinext build/runtime.

Runtime today: Docker image bundles Python **and** Node; `docker-entrypoint.sh` supervises two processes (`postbox-api` on :8000 internal + `npm start`/vinext on :3000 → published :8013); nginx routes `/api/*` → 8000, `/` → 8013.

### API surface (only 4 endpoints)

| Endpoint | Method | Purpose | Touches DB |
|---|---|---|---|
| `/api/health` | GET | liveness | no |
| `/api/ready` | GET | readiness | yes (`SELECT 1`) |
| `/api/auth/telegram` | POST | Telegram login → returns JWT (JSON) | yes |
| `/api/journal` | GET | current user's journal (list + stats) | yes |

There is **no** create/edit/delete/mark-received/note/correspondent endpoint.

### Layer classification

1. **Domain/business logic (reuse unchanged):** everything in `models/` — `User.register`, `count_approved`, `is_approved`, `approve_within_limit`; `MailItem.journal_page`, `journal_stats`, `mark_received`, `set_note`, `normalize_note`, `travel_days`, `status`, `journal_date`, `find_for_owner`; `Correspondent.for_owner`, `find_for_owner`, `find_or_create`. Plus `database/`, `config.py`, `logging.py`, Alembic migrations.
2. **HTTP/API transport (adapt):** `api.py` route handlers, request/response Pydantic models, CORS. Handlers get rewritten to return `TemplateResponse`/redirects; the underlying model calls stay identical.
3. **vinext-only (delete after migration):** the entire `web/` tree, `worker/`, vinext/vite/next config, `useAuth`, `telegram-web-app.ts`, Bearer/localStorage token handling, the Node half of `docker-entrypoint.sh`.
4. **Reuse unchanged:** models, database layer, config, logging, migrations, `auth.py` JWT create/decode, `globals.css` (moves to `/static` almost verbatim).
5. **Adapt:** `api.py` (split JSON health/ready from new HTML routes), `auth.py` (add cookie read/write helpers; wire real bot-token validation), `Dockerfile`/`docker-entrypoint.sh`/`docker-compose.yml`/nginx (single process/port — later phase).
6. **Delete after migration:** `web/`, Node/npm from image, dual-process entrypoint, `/api/journal` and `/api/auth/telegram` JSON variants (no external consumer), `web/tests/rendered-html.test.mjs`.

---

## 2. Current product / user flows

Only two flows are actually wired end-to-end today. The rest are **static mocks** (no handler, no fetch) or **modeled-but-unexposed** (business logic + tests exist, but no endpoint and no working UI).

| Flow | Current frontend | Current API | Business logic | DB entities | State | Target server route |
|---|---|---|---|---|---|---|
| Login (Telegram WebApp) | `/login` | `POST /api/auth/telegram` | `validate_telegram_signature`, `User.register`, `approve_within_limit`, `create_jwt_token` | User | **working** | `GET /login`, `POST /login` (set cookie, redirect) |
| Login (dev form) | `/login` dev form | `POST /api/auth/telegram` (dev_hash) | same | User | **working (dev)** | same `POST /login` |
| Logout | client `useAuth.logout` (clears localStorage) | — | — | — | **working (client-only)** | `POST /logout` (clear cookie, redirect) |
| Journal list + stats | `/` Journal tab / `JournalScreen` | `GET /api/journal` | `MailItem.journal_page`, `journal_stats`, `travel_days` | MailItem, Correspondent | **working (read-only)** | `GET /` (or `/journal`) → template |
| Journal filter (all/in-transit/received) | client-side array filter | — | `MailJournalFilter` (server-supported!) | MailItem | working (client) | `GET /?filter=…` server filter (no JS) |
| Journal detail | none (rows are not links; no `onClick`) | — | — | — | **not wired** | **OUT OF SCOPE (D2)** — no detail view exists today |
| Home dashboard | `/` Home tab | — | — (hardcoded `Маша`/`Анна`) | — | **mock only** | **OUT OF SCOPE (D2)** — `GET /` is the real journal + stats; drop fabricated cards |
| Create letter ("I sent"/"I received") | `/` New tab buttons | — | `MailItem.create`, `Correspondent.find_or_create` (exist, tested) | MailItem, Correspondent | **mock UI, modeled** | **OUT OF SCOPE (D2)** — deferred, evaluate post-migration |
| Mark received | none | — | `MailItem.mark_received` (exists, tested) | MailItem | **modeled, no UI** | **OUT OF SCOPE (D2)** |
| Edit note | none | — | `MailItem.set_note`, `normalize_note` (exist, tested) | MailItem | **modeled, no UI** | **OUT OF SCOPE (D2)** |
| Correspondents | none | — | `Correspondent.for_owner/find_or_create` (exist, tested) | Correspondent | **modeled, no UI** | **OUT OF SCOPE (D2)** |
| Registration limit / approval gate | surfaces error text on login | inside `POST /api/auth/telegram` | `count_approved`, `approve_within_limit` | User | **working** | inside `/auth/telegram` |
| Health / Ready | — | `GET /api/health`, `/api/ready` | `SELECT 1` | — | **working** | keep as JSON, unchanged |

**Scope (D2):** parity target = the genuinely-wired product only — **login, journal list + stats + server-side filter, logout, health/readiness, and the nav/layout that supports them**. Everything marked *OUT OF SCOPE* above (mocked home, create/mark-received/note, correspondents UI, journal detail) is **deferred**: not built during this migration, and not silently dropped either — the models/tests stay, and these are evaluated on product value *after* the server-rendered app is stable.

---

## 3. Target architecture (FastAPI + Jinja2)

- FastAPI routes return `fastapi.templating.Jinja2Templates` `TemplateResponse` (Jinja2 + Starlette).
- **POST → 303 See Other → GET** for state changes. In the parity scope the only such routes are auth: the Login Widget redirect (`GET /auth/telegram`) and `POST /logout`. No CRUD forms (D2).
- Server-side validation where it applies in scope: the login page re-renders with a message on rejected signature / awaiting-approval.
- Auth via **HttpOnly `Secure` `SameSite=Lax` cookie carrying the existing JWT** (see §5).
- `StaticFiles` mounted at `/static` for CSS, fonts, icons, and the tiny JS.
- Existing SQLAlchemy models/session, existing Alembic migrations — untouched.
- No new frontend framework. No HTMX/Alpine. Minimal vanilla JS only for: theme toggle (already vanilla today) and, if desired, the modal/sheet. Journal filtering becomes server-side via query param (no JS).

### Minimal JS that genuinely stays
- **Theme (light/dark/system):** already a tiny inline `<script>` in `layout.tsx` reading `localStorage` + `prefers-color-scheme`. Port verbatim into `base.html`. ~15 lines.
- Everything else (navigation, filtering, form submit, list rendering) is provided by normal browser behavior once server-rendered.

### Frontend behavior that simply disappears
- Client routing / tab state → real URLs.
- `fetch` + Bearer header + `useAuth` + localStorage token → cookie sent automatically by the browser.
- Client-side journal filtering → `?filter=` link + existing `MailJournalFilter`.
- Loading/skeleton/abort-controller states → server renders the final HTML.
- The whole vinext/Cloudflare-Worker runtime, RSC, image optimizer, etc.

---

## 4. Frontend-specific complexity that can be removed

Node/npm/vinext/vite/wrangler runtime; `react`, `react-dom`, `lucide-react`, `next`; `worker/index.ts`; RSC + image optimization; `useAuth`/`telegram-web-app.ts`/token plumbing; the second container process and port; nginx `/` vs `/api` split; `web/tests/rendered-html.test.mjs`. Net: one language, one process, one port, one healthcheck, one wheel.

---

## 5. Authentication model (LOCKED — D1)

**Decided: Telegram Login Widget (normal website) → server-side signature verification → existing Postbox JWT → HttpOnly, Secure, SameSite=Lax cookie → POST → 303 → GET. No localStorage, JWT never exposed to JS. No server-side sessions.**

Flow:
1. `GET /login` renders the Telegram **Login Widget** in redirect mode (`data-auth-url=/auth/telegram`, `data-telegram-login=<bot>`), plus (dev only) a fallback form.
2. Telegram redirects to `/auth/telegram` with signed fields (`id, first_name, last_name, username, photo_url, auth_date, hash`).
3. Server verifies the signature with the **real bot token** (`validate_telegram_signature`, Login Widget algorithm — already implemented), applies `User.register` + `approve_within_limit`, builds the JWT with the existing `create_jwt_token`.
4. Server responds **303** to `/` with `Set-Cookie: postbox_session=<jwt>; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=…`.
5. Protected routes read the cookie and `decode_jwt_token` (unchanged); missing/invalid → 303 `/login`.
6. `POST /logout` clears the cookie → 303 `/login`.

Why this over server-side sessions: reuses **all** of `auth.py` crypto with zero changes; stateless (fits SQLite single-node); HttpOnly removes the XSS token-theft exposure of today's localStorage. A sessions table/store is rejected — no benefit at ≤5 users, and it would add state + cleanup.

**Security bug to fix as part of this phase (gates completion):** today `api.py` calls `validate_telegram_signature(data, "", allow_dev_hash=True)` — empty token + `dev_hash_*` bypass — so anyone can mint a 365-day JWT. The fix: wire `POSTBOX_BOT_TOKEN` (already in `config.Settings`; add it to `WebSettings`), and disable the `dev_hash` path outside an explicit dev mode. This is the same code path the migration touches, so it is fixed here, not deferred.

Migration implications:
- **Reused unchanged:** `create_jwt_token`, `decode_jwt_token`, `WebSettings.jwt_secret_key`.
- **New (small):** a cookie-writing helper on login/logout and a `get_current_user` that reads the cookie instead of the `Authorization` header (the current header parser in `api.py:get_current_user` is replaced by a cookie read; the JWT decode is identical).
- **Disappears:** `useAuth.ts`, `telegram-web-app.ts` token bits, `localStorage` token get/set, the `Authorization: Bearer` header on `fetch`.

Other security items for the auth phase:
- **CSRF:** the only state-changing POST during a parity migration is `/logout` (login arrives as a Telegram-signed redirect). `SameSite=Lax` covers top-level navigations; add a per-form token on `/logout` for defence-in-depth. (No write-flow forms exist in scope — D2.)
- Cookie flags: `Secure` (behind nginx TLS), `HttpOnly`, `SameSite=Lax`, explicit `Max-Age`/`Path=/`.
- **Mechanism hygiene (D1):** standardize on Login Widget end-to-end; the WebApp-`initData` reader (`telegram-web-app.ts`) is deleted, not adapted. Never feed WebApp `initData` to the Login Widget verifier or vice-versa.

---

## 6. API endpoints: remain vs migrate

| Endpoint | Classification | Recommendation |
|---|---|---|
| `GET /api/health` | operational (monitoring) | **Remain JSON, unchanged** (Docker/Uptime-Kuma depend on it) |
| `GET /api/ready` | operational (Docker healthcheck) | **Remain JSON, unchanged** |
| `POST /api/auth/telegram` | needed-by-UI, returns token | **Become an HTML/redirect handler** (`POST /login` → set cookie → 303). Drop the JSON/token response (no external consumer) |
| `GET /api/journal` | needed-by-UI (only consumer is the SPA) | **Become the journal HTML route** (`GET /`). Drop JSON after migration — no external consumer |

No endpoint is a documented public API. To avoid duplicating logic across transports, HTML handlers call the **same model methods** the JSON handlers call today (`journal_page`, `journal_stats`, `register`, `approve_within_limit`) — business logic stays in the models, transports stay thin. Keep `/api/health` and `/api/ready` exactly as-is so deployment/monitoring contracts don't change.

---

## 7. Proposed target directory structure

```
src/postbox/
  api.py                # app factory; mounts StaticFiles; keeps /api/health,/api/ready JSON
  views.py              # NEW: HTML routes — GET /, GET /login, GET /auth/telegram, POST /logout
  auth.py               # + cookie read/write helpers; real bot-token validation
  templates/            # NEW (packaged in wheel)
    base.html           #   layout: <head>, theme script, nav, blocks
    login.html          #   Telegram Login Widget (+ dev fallback)
    journal.html        #   list + stats + filter links
    partials/
      mail_row.html
      icons.html        #   inline SVGs replacing lucide-react
    # NOTE: no write-flow templates (mail_form.html etc.) — out of scope (D2)
  static/               # NEW (packaged in wheel)
    css/app.css         #   from web/app/globals.css, near-verbatim
    js/theme.js         #   the ~15-line theme toggle
    fonts/onest-*.woff2 #   self-hosted (replaces @fontsource npm dep)
    img/                #   from docs/images or web assets
  models/ database/ config.py logging.py   # UNCHANGED
migrations/                                 # UNCHANGED
```

New Python deps: `jinja2`, `python-multipart` (form parsing). No other infra. Templates + static ship **inside** the package (already using `packages = [{include="postbox", from="src"}]`; add package-data include for `templates/` + `static/`).

---

## 8. Step-by-step migration phases

Each phase leaves the app runnable and testable. During phases 0–4 the vinext frontend keeps working (do not delete it yet).

**Phase 0 — Jinja + static infrastructure.**
Goal: templates render and `/static` serves, with zero behavior change.
Files: add `jinja2`,`python-multipart`; `api.py` (mount `StaticFiles`, init `Jinja2Templates`); add `templates/base.html`, `static/css/app.css` (copy of `globals.css`), `static/js/theme.js`, self-hosted font. 
Tests: base template renders 200 + contains title; `/static/css/app.css` served 200.
Acceptance: existing 4 endpoints unchanged; a throwaway `GET /_render_check` returns HTML. Remains operational: everything. Rollback: delete the new route/files.

**Phase 1 — Telegram Login Widget cookie auth (alongside existing) + security fix.**
Goal: real Telegram Login Widget verification → existing JWT → HttpOnly/Secure/SameSite=Lax cookie; add cookie-reading `get_current_user`. Keep the existing Bearer path temporarily so the SPA still works during transition.
Files: `config.py` (add `POSTBOX_BOT_TOKEN` to `WebSettings`), `auth.py` (cookie read/write helpers; keep `create_jwt_token`/`decode_jwt_token`/`validate_telegram_signature` unchanged), `views.py`/`api.py` (`GET /auth/telegram` verifies signed widget redirect → set cookie → 303 `/`; `POST /logout` clears cookie → 303). **Security fix (gates the phase):** verify with the real bot token; disable `dev_hash_*` outside an explicit dev flag.
Tests: correctly-signed widget payload → `Set-Cookie` HttpOnly + 303; tampered/expired `hash` → rejected; protected route with no cookie → 303 `/login`; with valid cookie → 200; registration-limit path → awaiting-approval page; `dev_hash` rejected when dev flag off.
Acceptance: cookie login works with real verification; the disabled-signature bug is closed; SPA (Bearer) still works. Remains operational: both auth paths. Rollback: remove cookie routes; SPA unaffected.

**Phase 2 — Server-render read pages (login + journal).**
Goal: `GET /login` (renders the Login Widget) and `GET /` (journal list + stats) render via templates using existing model methods; journal filter via `?filter=` using `MailJournalFilter`.
Files: `views.py`, `templates/login.html`, `templates/journal.html`, `partials/`. Reuse `journal_page`/`journal_stats`; no new domain code.
Tests: `GET /` unauth → 303; authed → 200 with mail rows + stats; `?filter=in_transit` filters server-side; empty-journal state; correspondent name, travel-days, status copy match the current UI strings.
Acceptance: the real product (login + journal list) fully usable with only the theme JS. Remains operational: SPA still available in parallel. Rollback: keep serving SPA.

_(No write-flow phase — D2. Create/mark-received/note/correspondents are deferred and evaluated only after the server-rendered app is stable.)_

**Phase 3 — Point nginx at the single app.**
Goal: serve everything from FastAPI; stop routing to the frontend port. (No Docker change yet — just nginx upstream.)
Tests: end-to-end through nginx to `/` and `/api/ready`.
Acceptance: production served entirely by Python. Remains operational: frontend container still running but unused. Rollback: restore nginx `/` → 8013.

**Phase 4 — Single-process runtime.**
Goal: remove Node/npm/vinext from the image; `docker-entrypoint.sh` runs only `postbox-api`; one port; one healthcheck; drop the frontend port publish.
Files: `Dockerfile`, `docker-entrypoint.sh`, `docker-compose.yml`.
Tests: image builds without Node; container starts single process; `/api/ready` 200; healthcheck green.
Acceptance: one runtime, one port. Rollback: previous image tag.

**Phase 5 — Delete obsolete code.**
Goal: remove `web/`, dead JSON endpoints (`/api/journal`, the JSON `POST /api/auth/telegram`, and the temporary Bearer `get_current_user`), `web/tests/*`, Node build steps, `.openai`/vinext config.
Tests: full Python suite + template/route tests green; no reference to removed paths.
Acceptance: repo is a single Python app. Rollback: git revert (frontend recoverable from history).

Ordering rationale: infra → auth(+security fix) → read pages → routing → runtime → deletion keeps a working, rollback-able app at every step and defers all irreversible deletion to the end. No write-flow phase (D2).

### Next step — Phase 0 execution checklist (ready to implement; nothing here changes behavior)

Prepared so the next session can execute Phase 0 mechanically. **Not yet implemented.** Phase 0 is purely additive Python-side scaffolding; the vinext frontend and all four existing endpoints are untouched, so it is fully rollback-able by deleting the added files.

1. **Deps:** add `jinja2` and `python-multipart` to `[tool.poetry.dependencies]`; `poetry lock` (do not hand-edit the lock). No frontend/Docker change.
2. **Package data:** add `templates/` and `static/` under `src/postbox/`; include them as package data so they ship in the wheel (extend the packaging smoke test to assert a template + a static file are present in the built wheel).
3. **App factory (`api.py`):** initialise `Jinja2Templates(directory=<pkg>/templates)` and `app.mount("/static", StaticFiles(directory=<pkg>/static), name="static")`. Keep `/api/health` and `/api/ready` exactly as they are.
4. **Base layout (`templates/base.html`):** `<head>` with the ported inline theme script, a `{% block content %}`, and a `<link>` to `/static/css/app.css`.
5. **Assets:** copy `web/app/globals.css` → `static/css/app.css` (near-verbatim); add `static/js/theme.js` (the ~15-line toggle); self-host the Onest `woff2` under `static/fonts/` with an `@font-face` (removes the `@fontsource` npm dependency at render time).
6. **Smoke route (temporary):** a throwaway `GET /_render_check` returning `TemplateResponse("base.html", …)` to prove rendering; removed at the end of Phase 2.

**Tests (Phase 0):** `GET /_render_check` → 200 `text/html` containing the base title; `GET /static/css/app.css` → 200; wheel-contents test asserts templates + static are packaged; existing suite stays green.

**Acceptance:** all pre-existing behavior identical; new render path proven. **Rollback:** delete the added files/route and the two deps — no other code references them.

**Do not** start Phase 1 (auth) in the same change: Phase 1 touches `auth.py`/`config.py` and the security fix, and must be reviewed and tested on its own.

---

## 9. Risks and edge cases

- **Telegram identity mechanism — RESOLVED (D1):** Login Widget redirect mode (`data-auth-url=/auth/telegram` → GET with HMAC-signed query → verify with real bot token → cookie → 303). The WebApp `initData` path is dropped, not adapted. Residual risk: the Login Widget requires the bot's domain to be registered with BotFather (`/setdomain`) for the target host — an operational prerequisite, not code. The disabled-signature bug is fixed in Phase 1.
- **CSRF** on `/logout` (the only in-scope state-changing POST): SameSite=Lax + per-form token.
- **Theme flash**: keep the inline pre-paint theme script in `<head>` (as today) to avoid FOUC.
- **Icons**: `lucide-react` components → inline SVG partials (Lucide SVGs are ISC-licensed); enumerate the ~20 icons used and ship as `partials/icons.html`.
- **Fonts**: replace `@fontsource-variable/onest` (npm) with a self-hosted `woff2` + `@font-face`.
- **Journal filter parity**: `MailJournalFilter` has `in_transit/outgoing/incoming/all`; current UI filter is `all/in_transit/received`. Map deliberately (received == has `received_at`) to avoid changing visible semantics.
- **SQLite concurrency**: unchanged; still single-node file DB. Fine.
- **Packaging**: templates/static must be included as package data in the wheel (verify with the existing packaging smoke test).
- **No data/schema change** in any phase — models and migrations are untouched.

---

## 10. Test strategy

Prefer behavior/flow tests over rendering details. Reuse the existing SQLite parity tests (they already cover persistence, FK/owner-scoping, CHECK constraints).

Add:
- **Auth:** login sets HttpOnly cookie; logout clears it; protected route → 303 when no/expired cookie; real signature validation accepts a correctly-signed payload and rejects a bad one.
- **Access control:** authed user only sees own journal; acting on another user's mail id → 404 (HTTP-level, complementing the model-level test).
- **Form validation:** invalid date combo re-renders form with error (not a 500); note too long/empty rejected.
- **Registration limit:** Nth+1 user gets the awaiting-approval page (HTTP-level; model level already tested).
- **CRUD/domain:** create → appears in journal; mark-received → status flips; note set/clear.
- **Redirects:** POST → 303 → GET (no double-submit).
- **Persistence:** covered by `test_sqlite_parity.py`.
- **Template rendering:** each route returns 200 + expected key copy; unauth `/` redirects.
- **Health/readiness:** existing tests keep passing unchanged.

Use FastAPI `TestClient` (sync) or httpx `ASGITransport` (async, as `test_api.py` already does) against a temp SQLite DB (as `test_sqlite_parity.py` already sets up).

Obsolete after migration: `web/tests/rendered-html.test.mjs` and the entire `npm test`/`npm run lint`/`npm run build` chain.

---

## 11. Expected production architecture after migration

```
Browser → nginx (TLS) → 127.0.0.1:8000 → uvicorn/Postbox
                                            ├── Jinja2 templates
                                            ├── /static (css, minimal js, fonts, icons)
                                            ├── model business logic
                                            └── SQLite (./data, aiosqlite)
```

Single container: Python runtime + `postbox` wheel (templates + static packaged) + migrations + one entrypoint (`postbox-api`). One published port, one `/api/ready` healthcheck. nginx becomes a plain reverse proxy to one upstream.

---

## 12. Dependencies that can ultimately be removed

- **npm/Node entirely** from the production image.
- Frontend packages: `vinext`, `next`, `react`, `react-dom`, `lucide-react`, `vite`, `wrangler`, `@cloudflare/vite-plugin`, `@vitejs/*`, `eslint*`, `typescript`, `react-server-dom-webpack`, `@fontsource-variable/onest`, all `@types/*`.
- The whole `web/` tree, `worker/`, `.openai/`, vinext/vite/next config.
- The second container process and the frontend port in `docker-compose.yml`.

Add (small): `jinja2`, `python-multipart`. Python runtime deps otherwise unchanged.

---

## 13. Decisions

**Locked:**
- **D1 — Telegram auth — LOCKED.** Telegram **Login Widget** (normal website) → server-side verification with the real `POSTBOX_BOT_TOKEN` → existing JWT → **HttpOnly, Secure, SameSite=Lax** cookie → POST → 303 → GET. No `localStorage`, JWT never exposed to JS. No server-side sessions. Keep existing JWT create/decode. Fix the disabled `dev_hash`/empty-token verification (security bug) in the auth phase. Do not mix Login Widget and WebApp `initData`.
- **D2 — no new features — LOCKED.** Parity only: login, journal list + stats + server-side filter, logout, health/readiness, supporting nav/layout. Mocked/modeled-but-unexposed flows (create/mark-received/note, correspondents UI, journal detail, home dashboard cards) are **deferred** — kept in the models/tests, not built now, not silently removed. `GET /` is the real journal + stats; the fabricated `Маша`/`Анна` cards are dropped (they were never real data).

**Still open (do not block the auth/read phases; settle before the affected phase):**
- **D3 — Drop the JSON API after migration?** No external consumer found. Recommendation: remove `/api/journal` and the JSON `POST /api/auth/telegram` in Phase 5; keep `/api/health` + `/api/ready` unchanged. Confirm no external integration relies on them before deleting.
- **D4 — CSRF for `/logout`:** SameSite=Lax + per-form token (recommended). Settle in Phase 1.
- **D5 — Icons & fonts:** inline SVG partials for the Lucide icons actually used; self-host Onest `woff2`. Settle in Phase 2. Both licenses permissive.
```
