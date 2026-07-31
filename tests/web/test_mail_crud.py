"""Tests for Tests for creating, reading, and editing mail items.."""

from __future__ import annotations

from datetime import date

import httpx

from postbox.api import create_app

from .conftest import (
    JWT_SECRET,
    _login,
    _seed_mail,
    app_client,
    build_settings,
)


async def test_create_form_requires_auth(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        response = await client.get("/mail/new")
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


async def test_create_outgoing_mail(tmp_path) -> None:
    today = date.today()
    settings = build_settings(tmp_path)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            await _login(client, telegram_id=60, first_name="Creator")
            await client.get("/")
            csrf = client.cookies.get("postbox_csrf")

            response = await client.post(
                "/mail",
                data={
                    "csrf_token": csrf,
                    "direction": "outgoing",
                    "correspondent": "Маша",
                    "mail_date": str(today),
                    "note": "Открытка из Петербурга",
                },
            )
            assert response.status_code == 303
            assert response.headers["location"] == "/"

            journal = await client.get("/")
    assert "Маша" in journal.text
    assert "Открытка из Петербурга" not in journal.text  # note not in list, only on detail


async def test_create_incoming_mail(tmp_path) -> None:
    today = date.today()
    settings = build_settings(tmp_path)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            await _login(client, telegram_id=61, first_name="Receiver")
            await client.get("/")
            csrf = client.cookies.get("postbox_csrf")

            response = await client.post(
                "/mail",
                data={
                    "csrf_token": csrf,
                    "direction": "incoming",
                    "correspondent": "Аня",
                    "mail_date": str(today),
                    "note": "",
                },
            )
            assert response.status_code == 303

            journal = await client.get("/")
    assert "Аня" in journal.text
    assert "Получено" in journal.text


async def test_create_outgoing_mail_with_full_geography(tmp_path) -> None:
    today = date.today()
    settings = build_settings(tmp_path)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            await _login(client, telegram_id=661)
            await client.get("/")
            csrf = client.cookies.get("postbox_csrf")
            response = await client.post(
                "/mail",
                data={
                    "csrf_token": csrf,
                    "direction": "outgoing",
                    "correspondent": "Geo Out",
                    "mail_date": str(today),
                    "origin_city": " Berlin ",
                    "origin_country": "de",
                    "destination_city": "Paris",
                    "destination_country": "fr",
                },
            )
            journal = await client.get("/")

    assert response.status_code == 303
    assert "Berlin, DE -&gt; Paris, FR" in journal.text


async def test_create_incoming_mail_with_full_geography(tmp_path) -> None:
    today = date.today()
    settings = build_settings(tmp_path)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            await _login(client, telegram_id=662)
            await client.get("/")
            csrf = client.cookies.get("postbox_csrf")
            response = await client.post(
                "/mail",
                data={
                    "csrf_token": csrf,
                    "direction": "incoming",
                    "correspondent": "Geo In",
                    "mail_date": str(today),
                    "origin_city": "Rome",
                    "origin_country": "it",
                    "destination_city": "Prague",
                    "destination_country": "cz",
                },
            )
            journal = await client.get("/")

    assert response.status_code == 303
    assert "Rome, IT -&gt; Prague, CZ" in journal.text


async def test_create_mail_with_partial_and_no_geography(tmp_path) -> None:
    today = date.today()
    settings = build_settings(tmp_path)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            await _login(client, telegram_id=663)
            await client.get("/")
            csrf = client.cookies.get("postbox_csrf")
            partial = await client.post(
                "/mail",
                data={
                    "csrf_token": csrf,
                    "direction": "outgoing",
                    "correspondent": "Partial",
                    "mail_date": str(today),
                    "origin_country": "de",
                    "destination_city": "Paris",
                },
            )
            none = await client.post(
                "/mail",
                data={
                    "csrf_token": csrf,
                    "direction": "outgoing",
                    "correspondent": "NoGeo",
                    "mail_date": str(today),
                },
            )
            journal = await client.get("/")

    assert partial.status_code == 303
    assert none.status_code == 303
    assert "DE -&gt; Paris" in journal.text
    assert "NoGeo" in journal.text


async def test_create_mail_rejects_invalid_country_and_preserves_geography(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        await _login(client, telegram_id=664)
        await client.get("/")
        csrf = client.cookies.get("postbox_csrf")
        response = await client.post(
            "/mail",
            data={
                "csrf_token": csrf,
                "direction": "outgoing",
                "correspondent": "Invalid Geo",
                "mail_date": str(date.today()),
                "origin_city": "Berlin",
                "origin_country": "deu",
                "destination_city": "Paris",
                "destination_country": "FR",
            },
        )

    assert response.status_code == 422
    assert "country code must be exactly 2 ASCII letters" in response.text
    assert 'value="Berlin"' in response.text
    assert 'value="deu"' in response.text


async def test_create_mail_validates_empty_correspondent(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        await _login(client, telegram_id=62)
        await client.get("/")
        csrf = client.cookies.get("postbox_csrf")
        response = await client.post(
            "/mail",
            data={"csrf_token": csrf, "direction": "outgoing", "correspondent": "  ", "mail_date": str(date.today())},
        )
    assert response.status_code == 422
    assert "Укажите имя адресата" in response.text


async def test_create_mail_validates_future_date(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        await _login(client, telegram_id=63)
        await client.get("/")
        csrf = client.cookies.get("postbox_csrf")
        response = await client.post(
            "/mail",
            data={
                "csrf_token": csrf,
                "direction": "outgoing",
                "correspondent": "Test",
                "mail_date": "2099-01-01",
            },
        )
    assert response.status_code == 422
    assert "будущем" in response.text


async def test_create_mail_requires_csrf(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        await _login(client, telegram_id=64)
        response = await client.post(
            "/mail",
            data={"csrf_token": "wrong", "direction": "outgoing", "correspondent": "X", "mail_date": str(date.today())},
        )
    assert response.status_code == 303
    assert "error=csrf" in response.headers["location"]


async def test_create_mail_preserves_values_on_error(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        await _login(client, telegram_id=65)
        await client.get("/")
        csrf = client.cookies.get("postbox_csrf")
        response = await client.post(
            "/mail",
            data={
                "csrf_token": csrf,
                "direction": "incoming",
                "correspondent": "Сергей",
                "mail_date": "",
                "note": "Тестовая заметка",
            },
        )
    assert response.status_code == 422
    assert "Сергей" in response.text
    assert "Тестовая заметка" in response.text


# --- Mail detail --------------------------------------------------------


async def test_detail_shows_item(tmp_path) -> None:
    today = date.today()
    settings = build_settings(tmp_path)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            await _login(client, telegram_id=70, first_name="Detail")
            from postbox.auth import decode_jwt_token

            token = client.cookies.get("postbox_session")
            user_id = decode_jwt_token(token, JWT_SECRET)["user_id"]
            await _seed_mail(app, user_id, [{"correspondent": "Детальная", "direction": "outgoing", "sent_at": today}])

            journal = await client.get("/")
            # Extract mail id from link
            import re

            match = re.search(r'href="/mail/(\d+)"', journal.text)
            assert match
            mail_id = match.group(1)

            response = await client.get(f"/mail/{mail_id}")
    assert response.status_code == 200
    assert "Детальная" in response.text
    assert "Исходящее письмо" in response.text
    assert 'class="detail-name__link" href="/correspondent/' in response.text
    assert "Отправлено" in response.text
    assert "<dt>Статус</dt>" not in response.text
    assert "Редактировать" in response.text


async def test_detail_other_user_returns_404(tmp_path) -> None:
    today = date.today()
    settings = build_settings(tmp_path)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            await _login(client, telegram_id=71, first_name="Owner")
            from postbox.auth import decode_jwt_token

            token = client.cookies.get("postbox_session")
            uid = decode_jwt_token(token, JWT_SECRET)["user_id"]
            await _seed_mail(app, uid, [{"correspondent": "Secret", "direction": "outgoing", "sent_at": today}])

            await _login(client, telegram_id=72, first_name="Intruder")
            response = await client.get("/mail/1")
    assert response.status_code == 404


# --- Notes --------------------------------------------------------------


async def test_add_note(tmp_path) -> None:
    today = date.today()
    settings = build_settings(tmp_path)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            await _login(client, telegram_id=90, first_name="Noter")
            await client.get("/")
            csrf = client.cookies.get("postbox_csrf")

            await client.post(
                "/mail",
                data={
                    "csrf_token": csrf,
                    "direction": "outgoing",
                    "correspondent": "Заметочный",
                    "mail_date": str(today),
                },
            )

            journal = await client.get("/")
            import re

            match = re.search(r'href="/mail/(\d+)"', journal.text)
            assert match
            mail_id = match.group(1)

            response = await client.post(
                f"/mail/{mail_id}/note",
                data={"csrf_token": csrf, "correspondent": "Заметочный", "note": "Привет из Москвы"},
            )
            assert response.status_code == 303

            detail = await client.get(f"/mail/{mail_id}")
    assert "Привет из Москвы" in detail.text


async def test_clear_note(tmp_path) -> None:
    today = date.today()
    settings = build_settings(tmp_path)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            await _login(client, telegram_id=91, first_name="Clearer")
            await client.get("/")
            csrf = client.cookies.get("postbox_csrf")

            await client.post(
                "/mail",
                data={
                    "csrf_token": csrf,
                    "direction": "outgoing",
                    "correspondent": "Очищаемый",
                    "mail_date": str(today),
                    "note": "Будет удалено",
                },
            )

            journal = await client.get("/")
            import re

            match = re.search(r'href="/mail/(\d+)"', journal.text)
            assert match
            mail_id = match.group(1)

            response = await client.post(
                f"/mail/{mail_id}/note",
                data={"csrf_token": csrf, "correspondent": "Очищаемый", "note": ""},
            )
            assert response.status_code == 303

            detail = await client.get(f"/mail/{mail_id}")
    assert "Будет удалено" not in detail.text


async def test_change_correspondent(tmp_path) -> None:
    today = date.today()
    settings = build_settings(tmp_path)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            await _login(client, telegram_id=94, first_name="Changer")
            await client.get("/")
            csrf = client.cookies.get("postbox_csrf")

            await client.post(
                "/mail",
                data={
                    "csrf_token": csrf,
                    "direction": "outgoing",
                    "correspondent": "Старое имя",
                    "mail_date": str(today),
                },
            )

            journal = await client.get("/")
            import re

            match = re.search(r'href="/mail/(\d+)"', journal.text)
            assert match
            mail_id = match.group(1)

            response = await client.post(
                f"/mail/{mail_id}/note",
                data={"csrf_token": csrf, "correspondent": "Новое имя", "note": ""},
            )
            assert response.status_code == 303

            detail = await client.get(f"/mail/{mail_id}")
    assert "Новое имя" in detail.text
    assert "Старое имя" not in detail.text


async def test_edit_mail_geography(tmp_path) -> None:
    today = date.today()
    settings = build_settings(tmp_path)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            await _login(client, telegram_id=941, first_name="GeoEditor")
            await client.get("/")
            csrf = client.cookies.get("postbox_csrf")

            await client.post(
                "/mail",
                data={
                    "csrf_token": csrf,
                    "direction": "outgoing",
                    "correspondent": "Route",
                    "mail_date": str(today),
                },
            )
            journal = await client.get("/")
            import re

            match = re.search(r'href="/mail/(\d+)"', journal.text)
            assert match
            mail_id = match.group(1)

            response = await client.post(
                f"/mail/{mail_id}/note",
                data={
                    "csrf_token": csrf,
                    "correspondent": "Route",
                    "note": "",
                    "origin_city": "Berlin",
                    "origin_country": "de",
                    "destination_city": "Paris",
                    "destination_country": "fr",
                },
            )
            detail = await client.get(f"/mail/{mail_id}")

    assert response.status_code == 303
    assert "Berlin, DE -&gt; Paris, FR" in detail.text


async def test_note_edit_form_requires_auth(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        response = await client.get("/mail/1/edit")
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


async def test_note_other_user_returns_404(tmp_path) -> None:
    today = date.today()
    settings = build_settings(tmp_path)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            await _login(client, telegram_id=92, first_name="Owner")
            from postbox.auth import decode_jwt_token

            token = client.cookies.get("postbox_session")
            uid = decode_jwt_token(token, JWT_SECRET)["user_id"]
            await _seed_mail(app, uid, [{"correspondent": "NoteTarget", "direction": "outgoing", "sent_at": today}])

            await _login(client, telegram_id=93, first_name="Other")
            await client.get("/")
            csrf = client.cookies.get("postbox_csrf")
            response = await client.post(
                "/mail/1/note", data={"csrf_token": csrf, "correspondent": "Hacked", "note": "Hacked"}
            )
    assert response.status_code == 404


# --- HTML escaping ------------------------------------------------------


async def test_xss_in_correspondent_escaped(tmp_path) -> None:
    settings = build_settings(tmp_path)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            await _login(client, telegram_id=95, first_name="XSS")
            await client.get("/")
            csrf = client.cookies.get("postbox_csrf")

            await client.post(
                "/mail",
                data={
                    "csrf_token": csrf,
                    "direction": "outgoing",
                    "correspondent": '<script>alert("xss")</script>',
                    "mail_date": str(date.today()),
                },
            )
            journal = await client.get("/")
    assert '<script>alert("xss")</script>' not in journal.text
    assert "&lt;script&gt;" in journal.text


# --- Empty state variants -----------------------------------------------


async def test_empty_journal_has_create_cta(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        await _login(client, telegram_id=96)
        response = await client.get("/")
    assert "Журнал пока пуст" in response.text
    assert 'href="/mail/new"' in response.text


# --- Flash messages -----------------------------------------------------


async def test_create_two_mails_same_correspondent(tmp_path) -> None:
    today = date.today()
    settings = build_settings(tmp_path)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            await _login(client, telegram_id=99, first_name="Double")
            await client.get("/")
            csrf = client.cookies.get("postbox_csrf")

            await client.post(
                "/mail",
                data={"csrf_token": csrf, "direction": "outgoing", "correspondent": "Ру", "mail_date": str(today)},
            )
            response = await client.post(
                "/mail",
                data={"csrf_token": csrf, "direction": "outgoing", "correspondent": "Ру", "mail_date": str(today)},
            )
            assert response.status_code == 303

            journal = await client.get("/")
    assert journal.text.count("Ру") >= 2


async def test_flash_after_create(tmp_path) -> None:
    settings = build_settings(tmp_path)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            await _login(client, telegram_id=98, first_name="Flash")
            await client.get("/")
            csrf = client.cookies.get("postbox_csrf")

            create_resp = await client.post(
                "/mail",
                data={
                    "csrf_token": csrf,
                    "direction": "outgoing",
                    "correspondent": "Флешка",
                    "mail_date": str(date.today()),
                },
            )
            client.cookies.update(create_resp.cookies)
            journal = await client.get("/")
    assert "Письмо добавлено" in journal.text


# --- Correspondent detail page ---
