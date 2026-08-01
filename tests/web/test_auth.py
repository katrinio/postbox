"""Tests for Tests for authentication and session management.."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt

from postbox.models import User

from .conftest import (
    HUB_AUTH_SECRET,
    _login,
    app_client,
    build_settings,
    create_hub_auth_url,
)


async def test_get_login_returns_html(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        response = await client.get("/login")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Вход через The Hub Bot пока не настроен" in response.text


async def test_login_shows_hub_bot_link_when_configured(tmp_path) -> None:
    settings = build_settings(tmp_path, hub_bot_url="https://t.me/hub_test_bot?start=postbox")
    async with app_client(settings) as client:
        response = await client.get("/login")
    assert response.status_code == 200
    assert "telegram-widget.js" not in response.text
    assert 'href="https://t.me/hub_test_bot?start=postbox"' in response.text
    assert "Открыть The Hub" in response.text


async def test_login_handles_missing_hub_bot_link(tmp_path) -> None:
    settings = build_settings(tmp_path, hub_bot_url=None)
    async with app_client(settings) as client:
        response = await client.get("/login")
    assert response.status_code == 200
    assert "telegram-widget.js" not in response.text
    assert "Вход через The Hub Bot пока не настроен" in response.text


async def test_direct_telegram_auth_route_is_not_available(tmp_path) -> None:
    settings = build_settings(tmp_path)
    async with app_client(settings) as client:
        response = await client.get("/auth/telegram")
    assert response.status_code == 404


async def test_unauthenticated_home_redirects_to_login(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        response = await client.get("/")
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


# --- Authentication -----------------------------------------------------------


async def test_logout_clears_cookie(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        await _login(client, telegram_id=6)
        await client.get("/")
        csrf = client.cookies.get("postbox_csrf")
        response = await client.post("/logout", data={"csrf_token": csrf})
    assert response.status_code == 303
    assert response.headers["location"] == "/login"
    set_cookie = response.headers["set-cookie"]
    assert set_cookie.startswith("postbox_session=")
    assert 'postbox_session="";' in set_cookie or "Max-Age=0" in set_cookie or "expires=" in set_cookie.lower()


async def test_logout_without_csrf_is_rejected(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        await _login(client, telegram_id=7)
        await client.get("/")
        response = await client.post("/logout", data={"csrf_token": "wrong-token"})
    assert response.status_code == 303
    assert response.headers["location"] == "/login?error=csrf"


# --- Hub authentication -------------------------------------------------------


async def test_hub_auth_creates_user_with_profile_claims(tmp_path) -> None:
    settings = build_settings(tmp_path)
    async with app_client(settings) as client:
        response = await client.get(
            create_hub_auth_url(
                123456789,
                profile_claims={
                    "telegram_id": 123456789,
                    "first_name": "Katrin",
                    "last_name": "Example",
                    "username": "katrin_dev",
                    "language_code": "ru",
                },
            )
        )

        assert response.status_code == 303
        async with client._transport.app.state.database.session_factory() as session:
            user = await User.find_by_telegram_id(session, 123456789)

        assert user is not None
        assert user.first_name == "Katrin"
        assert user.last_name == "Example"
        assert user.username == "katrin_dev"
        assert user.language_code == "ru"


async def test_hub_auth_updates_existing_user_profile(tmp_path) -> None:
    settings = build_settings(tmp_path)
    async with app_client(settings) as client:
        await client.get(
            create_hub_auth_url(
                2001,
                profile_claims={
                    "telegram_id": 2001,
                    "first_name": "Old",
                    "last_name": "Name",
                    "username": "old_username",
                    "language_code": "en",
                },
            )
        )
        await client.get(
            create_hub_auth_url(
                2001,
                profile_claims={
                    "telegram_id": 2001,
                    "first_name": "New",
                    "last_name": "Profile",
                    "username": "new_username",
                    "language_code": "ru",
                },
            )
        )

        async with client._transport.app.state.database.session_factory() as session:
            user = await User.find_by_telegram_id(session, 2001)

        assert user is not None
        assert user.first_name == "New"
        assert user.last_name == "Profile"
        assert user.username == "new_username"
        assert user.language_code == "ru"


async def test_hub_auth_syncs_changed_username(tmp_path) -> None:
    settings = build_settings(tmp_path)
    async with app_client(settings) as client:
        await client.get(
            create_hub_auth_url(2002, profile_claims={"telegram_id": 2002, "first_name": "User", "username": "old"})
        )
        await client.get(
            create_hub_auth_url(2002, profile_claims={"telegram_id": 2002, "first_name": "User", "username": "new"})
        )

        async with client._transport.app.state.database.session_factory() as session:
            user = await User.find_by_telegram_id(session, 2002)

        assert user is not None
        assert user.username == "new"


async def test_hub_auth_handles_nullable_profile_claims(tmp_path) -> None:
    settings = build_settings(tmp_path)
    async with app_client(settings) as client:
        await client.get(
            create_hub_auth_url(
                2003,
                profile_claims={
                    "telegram_id": 2003,
                    "first_name": "Nullable",
                    "last_name": None,
                    "username": None,
                    "language_code": None,
                },
            )
        )

        async with client._transport.app.state.database.session_factory() as session:
            user = await User.find_by_telegram_id(session, 2003)

        assert user is not None
        assert user.first_name == "Nullable"
        assert user.last_name is None
        assert user.username is None
        assert user.language_code is None


async def test_old_hub_token_does_not_clear_existing_profile(tmp_path) -> None:
    settings = build_settings(tmp_path)
    async with app_client(settings) as client:
        await client.get(
            create_hub_auth_url(
                2004,
                profile_claims={
                    "telegram_id": 2004,
                    "first_name": "Saved",
                    "last_name": "Person",
                    "username": "saved_user",
                    "language_code": "ru",
                },
            )
        )
        await client.get(create_hub_auth_url(2004))

        async with client._transport.app.state.database.session_factory() as session:
            user = await User.find_by_telegram_id(session, 2004)

        assert user is not None
        assert user.first_name == "Saved"
        assert user.last_name == "Person"
        assert user.username == "saved_user"
        assert user.language_code == "ru"


async def test_old_hub_token_uses_fallback_only_for_new_user(tmp_path) -> None:
    settings = build_settings(tmp_path)
    async with app_client(settings) as client:
        await client.get(create_hub_auth_url(2005))

        async with client._transport.app.state.database.session_factory() as session:
            user = await User.find_by_telegram_id(session, 2005)

        assert user is not None
        assert user.first_name == "Telegram User"
        assert user.last_name is None
        assert user.username is None


async def test_display_name_fallback_order(tmp_path) -> None:
    settings = build_settings(tmp_path)
    async with app_client(settings) as client:
        await client.get(
            create_hub_auth_url(
                2006,
                profile_claims={
                    "telegram_id": 2006,
                    "first_name": "Katrin",
                    "last_name": "Example",
                    "username": "katrin_dev",
                },
            )
        )
        response = await client.get("/")
        assert "Katrin Example" in response.text

        async with client._transport.app.state.database.session_factory() as session:
            user = await User.find_by_telegram_id(session, 2006)
            assert user is not None
            user.first_name = ""
            user.last_name = None
            user.username = "katrin_dev"
            await user.save(session)
            await session.commit()

        response = await client.get("/")
        assert "@katrin_dev" in response.text

        async with client._transport.app.state.database.session_factory() as session:
            user = await User.find_by_telegram_id(session, 2006)
            assert user is not None
            user.username = None
            await user.save(session)
            await session.commit()

        response = await client.get("/")
        assert "Telegram User" in response.text


async def test_mismatched_sub_and_telegram_id_rejects_login(tmp_path) -> None:
    settings = build_settings(tmp_path)
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": "3001",
            "telegram_id": 3002,
            "aud": "postbox",
            "iss": "the-hub-bot",
            "iat": now,
            "exp": now + timedelta(minutes=5),
        },
        HUB_AUTH_SECRET,
        algorithm="HS256",
    )

    async with app_client(settings) as client:
        response = await client.get(f"/auth/hub?token={token}")

        assert response.status_code == 303
        assert response.headers["location"] == "/login?error=hub_auth"
        assert "postbox_session" not in client.cookies
        async with client._transport.app.state.database.session_factory() as session:
            assert await User.find_by_telegram_id(session, 3001) is None
            assert await User.find_by_telegram_id(session, 3002) is None


async def test_invalid_hub_signature_does_not_sync_user(tmp_path) -> None:
    settings = build_settings(tmp_path)
    async with app_client(settings) as client:
        response = await client.get(
            create_hub_auth_url(
                3003,
                secret="wrong-secret-at-least-32-bytes-long",
                profile_claims={"telegram_id": 3003, "first_name": "Invalid"},
            )
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/login?error=hub_auth"
        assert "postbox_session" not in client.cookies
        async with client._transport.app.state.database.session_factory() as session:
            assert await User.find_by_telegram_id(session, 3003) is None


async def test_wrong_aud_iss_and_expired_hub_tokens_do_not_sync_user(tmp_path) -> None:
    settings = build_settings(tmp_path)
    now = datetime.now(UTC)
    payloads = [
        {"sub": "3004", "aud": "other", "iss": "the-hub-bot", "iat": now, "exp": now + timedelta(minutes=5)},
        {"sub": "3005", "aud": "postbox", "iss": "other", "iat": now, "exp": now + timedelta(minutes=5)},
        {"sub": "3006", "aud": "postbox", "iss": "the-hub-bot", "iat": now, "exp": now - timedelta(minutes=1)},
    ]

    async with app_client(settings) as client:
        for payload in payloads:
            payload.update({"telegram_id": int(payload["sub"]), "first_name": "Rejected"})
            token = jwt.encode(payload, HUB_AUTH_SECRET, algorithm="HS256")
            response = await client.get(f"/auth/hub?token={token}")
            assert response.status_code == 303
            assert response.headers["location"] == "/login?error=hub_auth"

        async with client._transport.app.state.database.session_factory() as session:
            assert await User.find_by_telegram_id(session, 3004) is None
            assert await User.find_by_telegram_id(session, 3005) is None
            assert await User.find_by_telegram_id(session, 3006) is None


async def test_profile_one_user_cannot_update_another_user(tmp_path) -> None:
    settings = build_settings(tmp_path)
    async with app_client(settings) as client:
        await client.get(create_hub_auth_url(4001, profile_claims={"telegram_id": 4001, "first_name": "First"}))

        response = await client.get(
            create_hub_auth_url(
                4002,
                profile_claims={"telegram_id": 4001, "first_name": "Wrong"},
            )
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/login?error=hub_auth"
        async with client._transport.app.state.database.session_factory() as session:
            first = await User.find_by_telegram_id(session, 4001)
            second = await User.find_by_telegram_id(session, 4002)

        assert first is not None
        assert first.first_name == "First"
        assert second is None


async def test_db_error_does_not_authorize_user(tmp_path, monkeypatch) -> None:
    settings = build_settings(tmp_path)

    async def fail_sync(*args, **kwargs):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr("postbox.views.sync_user_from_hub_claims", fail_sync)

    async with app_client(settings) as client:
        response = await client.get(
            create_hub_auth_url(5001, profile_claims={"telegram_id": 5001, "first_name": "DbError"})
        )

    assert response.status_code == 303
    assert response.headers["location"] == "/login?error=hub_auth"
    assert "postbox_session" not in client.cookies


async def test_hub_auth_logs_do_not_include_token(tmp_path, caplog) -> None:
    settings = build_settings(tmp_path)
    auth_url = create_hub_auth_url(5002, secret="wrong-secret-at-least-32-bytes-long")
    token = auth_url.split("token=", 1)[1]

    async with app_client(settings) as client:
        await client.get(auth_url)

    assert token not in caplog.text


# --- Existing behavior preserved ----------------------------------------------


# --- JWT security ------------------------------------------------------------


async def test_jwt_with_wrong_algorithm_rejected(tmp_path) -> None:
    import jwt

    settings = build_settings(tmp_path)
    bad_token = jwt.encode({"user_id": 1}, settings.jwt_secret_key, algorithm="HS512")
    async with app_client(settings) as client:
        client.cookies.set("postbox_session", bad_token)
        response = await client.get("/")
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


async def test_jwt_tampered_signature_rejected(tmp_path) -> None:
    import jwt

    settings = build_settings(tmp_path)
    good_token = jwt.encode({"user_id": 1}, settings.jwt_secret_key, algorithm="HS256")
    tampered = good_token[:-10] + "0123456789"
    async with app_client(settings) as client:
        client.cookies.set("postbox_session", tampered)
        response = await client.get("/")
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


async def test_jwt_expired_rejected(tmp_path) -> None:
    from datetime import UTC, datetime

    import jwt

    settings = build_settings(tmp_path)
    expired = jwt.encode(
        {"user_id": 1, "exp": datetime.now(UTC) - timedelta(hours=1)},
        settings.jwt_secret_key,
        algorithm="HS256",
    )
    async with app_client(settings) as client:
        client.cookies.set("postbox_session", expired)
        response = await client.get("/")
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


# --- Existing behavior preserved -------------------------------------------


async def test_dev_login_disabled_returns_404(tmp_path) -> None:
    async with app_client(build_settings(tmp_path, dev_login=False)) as client:
        response = await client.post("/login", data={"telegram_id": "1", "first_name": "X", "csrf_token": "x"})
    assert response.status_code == 404


# --- Removed legacy endpoints return 404/405 ---------------------------------
