# Security & Authentication

## Trust Model

Postbox authenticates users through Telegram. The authentication chain is:

```
Telegram account
    ↓ (cryptographic verification)
The Hub identity (telegram_id)
    ↓ (local session creation)
Postbox application session (JWT in HttpOnly cookie)
    ↓ (authorization checks)
User data (ownership validation)
```

### Components

1. **Telegram cryptographic verification** — server validates HMAC signature of Telegram data
2. **HTTPS only** — all authentication happens over encrypted connections
3. **Application session** — stateless JWT stored in secure HttpOnly cookie
4. **CSRF protection** — double-submit cookie for state-changing requests
5. **Ownership checks** — every query validates user owns the requested data

---

## 1. Telegram Authentication

### How it works

1. User clicks "Login with Telegram"
2. Telegram app/web opens and asks permission
3. User confirms
4. Browser redirects to `/auth/telegram?id=...&hash=...&auth_date=...&...`
5. Server verifies HMAC signature with `bot_token`
6. Server checks `auth_date` is recent (within 24 hours)
7. If valid, create local JWT session

### Security properties

- **Signature verification**: `hmac.compare_digest()` prevents timing attacks
- **Bot token secret**: Never sent to client; server-only
- **Auth date validation**: Rejects replayed/stale logins
- **No dev bypass in production**: `POSTBOX_DEV_LOGIN=false` enforced

### Configuration

Required environment variables:

```bash
POSTBOX_BOT_TOKEN=123456789:ABCDEFGHIJKLMNOP  # From BotFather
POSTBOX_BOT_USERNAME=@my_postbox_bot           # Bot username
POSTBOX_PUBLIC_URL=https://postbox.example.com # For bot domain
```

### Dev bypass (development only)

When `POSTBOX_DEV_LOGIN=true`, a test form accepts `telegram_id + first_name` without Telegram.

**This must be `false` in production.**

---

## 2. Application Session (JWT)

### Structure

JWT contains only:

- `user_id` — internal database ID
- `telegram_id` — external stable identifier
- `iat` — issued at (Unix timestamp)
- `exp` — expires (Unix timestamp, default 365 days)

### Signing

- Algorithm: HS256 (HMAC-SHA256)
- Secret: `POSTBOX_JWT_SECRET_KEY` (generate with `openssl rand -hex 32`)
- Never stored in git

### Storage

Token is stored **only** in cookie:

```
Set-Cookie: postbox_session=<jwt>; 
  HttpOnly;        // JavaScript cannot read
  Secure;          // HTTPS only (in production)
  SameSite=Lax;    // Some cross-site requests allowed
  Path=/;          // Available to all routes
```

Token is **never** stored in:

- localStorage
- sessionStorage
- URL parameters
- Request headers (except as-is from cookie)

### Validation

On each authenticated request:

1. Extract JWT from `postbox_session` cookie
2. Verify signature with `POSTBOX_JWT_SECRET_KEY`
3. Check `exp` is in future
4. Reject if invalid or expired

### Revocation

JWT is stateless — no revocation list. Tradeoff: cannot instantly logout without additional infrastructure.

For this personal application, the 365-day expiry + logout (cookie deletion) is acceptable.

---

## 3. CSRF Protection

### Method

Double-submit cookie pattern:

1. Server generates `csrf_token = secrets.token_urlsafe(32)`
2. Sends as `postbox_csrf` cookie (HttpOnly, SameSite=Lax)
3. Form includes hidden `<input name="csrf_token" value="...">`
4. On POST, server compares form value to cookie value with `hmac.compare_digest()`

### Protected routes

All state-changing operations:

- `POST /mail` (create)
- `POST /mail/{id}/note` (update note)
- `POST /mail/{id}/received` (mark received)
- `POST /logout` (logout)

### Validation

```python
_verify_csrf(request, csrf_token_from_form)
```

Rejects if:

- Token missing from form
- Token missing from cookie
- Tokens don't match (constant-time comparison)

---

## 4. Logout

POST to `/logout` with valid CSRF token:

1. Deletes `postbox_session` cookie (Set-Cookie with Max-Age=0)
2. Deletes `postbox_csrf` cookie
3. Redirects to `/login`

Does not log user out of Telegram.

---

## 5. Data Ownership

Every query validates the requesting user owns the data:

```python
item = await MailItem.find_for_owner(
    session,
    owner_id=current_user_id,
    mail_id=requested_mail_id
)
if item is None:
    raise HTTPException(status_code=404)
```

Returns 404 if:

- Mail item doesn't exist
- Mail item belongs to a different user
- Correspondent belongs to a different user

---

## 6. Secrets Management

### Never commit

```
.gitignore:
.env
.env.*.local
*.key
secrets/
```

### Production setup

Provide secrets via environment variables (Docker secrets, CI/CD provider, etc):

```bash
export POSTBOX_JWT_SECRET_KEY="$(openssl rand -hex 32)"
export POSTBOX_BOT_TOKEN="123456789:ABCDEFGHIJKLMNOP"
export POSTBOX_BOT_USERNAME="@my_bot"
export POSTBOX_PUBLIC_URL="https://postbox.example.com"
```

### Logging

Never log:

- JWT tokens
- Bot token
- CSRF tokens
- Telegram auth payload (only log success/failure)
- Passwords (if added)

---

## 7. Testing

Security tests verify:

- ✅ Valid Telegram payload accepted
- ✅ Tampered payload rejected
- ✅ Stale auth_date rejected
- ✅ dev_hash rejected when not allowed
- ✅ JWT with wrong algorithm rejected
- ✅ Expired JWT rejected
- ✅ Tampered JWT rejected
- ✅ CSRF missing → request rejected
- ✅ CSRF mismatch → request rejected
- ✅ User A cannot access user B's data

Run all tests:

```bash
pytest tests/test_web.py -q
```

---

## 8. HTTPS & Reverse Proxy

### Production requirement

All authentication requires HTTPS. HTTP redirects to HTTPS.

### Reverse proxy headers

Nginx should pass:

```nginx
proxy_set_header Host $host;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
```

### Application config

App trusts `X-Forwarded-Proto` only from known reverse proxy (127.0.0.1 by default).

---

## 9. Future: Multi-app identity

When multiple apps (Postbox, Traect, etc.) share The Hub:

- Single Telegram identity = `telegram_id`
- Each app has separate database and session cookie
- Compromise of one app session doesn't compromise others

No shared authentication database; each app is responsible for its authorization.

---

## Checklist: Before production deployment

- [ ] `POSTBOX_DEV_LOGIN=false` in production config
- [ ] `POSTBOX_JWT_SECRET_KEY` is strong random 64-char hex string
- [ ] `POSTBOX_BOT_TOKEN` and `POSTBOX_BOT_USERNAME` are set
- [ ] Bot is registered on domain with `/setdomain` in BotFather
- [ ] HTTPS is enabled on reverse proxy
- [ ] `Secure` flag in cookies is `true`
- [ ] Logs don't contain JWT, tokens, or Telegram payloads
- [ ] All tests pass
- [ ] `.env` is in `.gitignore` (never committed)
