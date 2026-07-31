"""Tests for Tests for correspondents management and detail pages.."""

from __future__ import annotations

from datetime import date, timedelta

import httpx

from postbox.api import create_app
from postbox.models import Correspondent

from .conftest import (
    _current_user_id,
    _has_nested_anchor,
    _login,
    _seed_mail,
    app_client,
    build_settings,
)


async def test_top_navigation_links_journal_and_correspondents(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        await _login(client, telegram_id=76)
        journal = await client.get("/")
        correspondents = await client.get("/correspondents")

    assert 'href="/correspondents"' in journal.text
    assert 'href="/"' in correspondents.text
    assert "Адресная" in journal.text
    assert "Журнал" in correspondents.text


async def test_correspondents_requires_auth(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        response = await client.get("/correspondents")
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


async def test_correspondents_list_counts_scope_and_sort(tmp_path) -> None:
    today = date.today()
    settings = build_settings(tmp_path)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            await _login(client, telegram_id=70)
            owner_id = _current_user_id(client)
            await _seed_mail(
                app,
                owner_id,
                [
                    {"correspondent": "мария", "direction": "outgoing", "sent_at": today},
                    {"correspondent": "мария", "direction": "incoming", "received_at": today},
                    {"correspondent": "Анна", "direction": "incoming", "received_at": today},
                    {"correspondent": "борис", "direction": "outgoing", "sent_at": today},
                ],
            )
            async with app.state.database.session_factory() as session:
                await Correspondent.create(session, owner_id=owner_id, name="Zero")
                await session.commit()

            await _login(client, telegram_id=71)
            other_id = _current_user_id(client)
            await _seed_mail(app, other_id, [{"correspondent": "Secret", "direction": "outgoing", "sent_at": today}])

            await _login(client, telegram_id=70)
            response = await client.get("/correspondents")

    assert response.status_code == 200
    assert (
        response.text.index("Zero")
        < response.text.index("Анна")
        < response.text.index("борис")
        < response.text.index("мария")
    )
    assert "Secret" not in response.text
    assert 'aria-label="Отправлено: 0">↗ 0' in response.text
    assert 'aria-label="Получено: 0">↙ 0' in response.text
    assert 'aria-label="Отправлено: 0">↗ 0' in response.text
    assert 'aria-label="Получено: 1">↙ 1' in response.text
    assert 'aria-label="Отправлено: 1">↗ 1' in response.text
    assert 'aria-label="Получено: 0">↙ 0' in response.text
    assert 'class="correspondent-row" href="/correspondent/' in response.text


async def test_correspondents_empty_state(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        await _login(client, telegram_id=72)
        response = await client.get("/correspondents")

    assert response.status_code == 200
    assert "Адресная пока пуста" in response.text
    assert "Они появятся здесь после добавления письма" in response.text


async def test_correspondent_detail_shows_stats_and_history(tmp_path) -> None:
    today = date.today()
    settings = build_settings(tmp_path)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            await _login(client, telegram_id=77)
            user_id = _current_user_id(client)
            await _seed_mail(
                app,
                user_id,
                [
                    {"correspondent": "Alice", "direction": "outgoing", "sent_at": today, "origin_city": "Newest"},
                    {
                        "correspondent": "Alice",
                        "direction": "incoming",
                        "received_at": today - timedelta(days=1),
                        "origin_city": "Middle",
                    },
                    {
                        "correspondent": "Alice",
                        "direction": "outgoing",
                        "sent_at": today - timedelta(days=2),
                        "origin_city": "Oldest",
                    },
                ],
            )

            async with app.router.lifespan_context(app), app.state.database.session_factory() as session:
                from postbox.models import Correspondent

                corr = await Correspondent.find_or_create(session, owner_id=user_id, name="Alice")
                correspondent_id = corr.id

            response = await client.get(f"/correspondent/{correspondent_id}")

    assert response.status_code == 200
    assert 'href="/correspondents">← Адресная' in response.text
    assert "Alice" in response.text
    assert 'aria-label="Отправлено: 2">↗ 2' in response.text
    assert 'aria-label="Получено: 1">↙ 1' in response.text
    assert response.text.index("Newest") < response.text.index("Middle") < response.text.index("Oldest")
    assert 'class="journal-row__name"' not in response.text
    assert 'class="journal-row__link" href="/mail/' in response.text
    assert "Отправлено · <time" in response.text
    assert "Получено · <time" in response.text
    assert "Исходящее" not in response.text
    assert "Входящее" not in response.text
    assert "Заметки пока нет" in response.text
    assert 'aria-label="Редактировать заметку"' in response.text
    assert 'maxlength="250"' in response.text
    assert not _has_nested_anchor(response.text)


async def test_correspondent_detail_shows_existing_note_safely(tmp_path) -> None:
    today = date.today()
    settings = build_settings(tmp_path)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            await _login(client, telegram_id=177)
            user_id = _current_user_id(client)
            await _seed_mail(app, user_id, [{"correspondent": "SafeNote", "direction": "outgoing", "sent_at": today}])
            async with app.state.database.session_factory() as session:
                corr = await Correspondent.find_for_owner(session, owner_id=user_id, correspondent_id=1)
                if corr is None:
                    corr = await Correspondent.find_or_create(session, owner_id=user_id, name="SafeNote")
                correspondent_id = corr.id
                corr.note = "Любит архитектуру.\n<script>alert('x')</script>"
                await corr.save(session)
                await session.commit()

            response = await client.get(f"/correspondent/{correspondent_id}")

    assert response.status_code == 200
    assert "Любит архитектуру." in response.text
    assert "<script>alert('x')</script>" not in response.text
    assert "&lt;script&gt;" in response.text
    assert 'class="correspondent-note__text"' in response.text
    assert "<textarea disabled" not in response.text
    assert 'aria-label="Редактировать заметку"' in response.text
    assert f'action="/correspondent/{correspondent_id}/note"' in response.text
    assert 'method="post"' in response.text


async def test_correspondent_detail_other_user_returns_404(tmp_path) -> None:
    settings = build_settings(tmp_path)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            await _login(client, telegram_id=78)
            user_id_1 = _current_user_id(client)
            await _seed_mail(
                app,
                user_id_1,
                [{"correspondent": "Bob", "direction": "outgoing", "sent_at": date.today()}],
            )

            async with app.router.lifespan_context(app), app.state.database.session_factory() as session:
                from postbox.models import Correspondent

                corr = await Correspondent.find_or_create(session, owner_id=user_id_1, name="Bob")
                correspondent_id = corr.id

            client.cookies.clear()
            await _login(client, telegram_id=79)

            response = await client.get(f"/correspondent/{correspondent_id}")

    assert response.status_code == 404


async def test_correspondent_detail_unknown_returns_404(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        await _login(client, telegram_id=82)
        response = await client.get("/correspondent/999")

    assert response.status_code == 404


async def test_correspondent_save_note(tmp_path) -> None:
    today = date.today()
    settings = build_settings(tmp_path)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            await _login(client, telegram_id=80)
            user_id = _current_user_id(client)
            await _seed_mail(
                app,
                user_id,
                [{"correspondent": "Charlie", "direction": "outgoing", "sent_at": today}],
            )

            await client.get("/")
            csrf = client.cookies.get("postbox_csrf")

            async with app.router.lifespan_context(app), app.state.database.session_factory() as session:
                from postbox.models import Correspondent

                corr = await Correspondent.find_or_create(session, owner_id=user_id, name="Charlie")
                correspondent_id = corr.id

            response = await client.post(
                f"/correspondent/{correspondent_id}/note",
                data={"csrf_token": csrf, "note": "  Важный контакт  "},
                follow_redirects=False,
            )

    assert response.status_code == 303
    assert response.headers["location"] == f"/correspondent/{correspondent_id}"

    async with app.router.lifespan_context(app), app.state.database.session_factory() as session:
        from postbox.models import Correspondent

        corr = await Correspondent.find_for_owner(session, owner_id=user_id, correspondent_id=correspondent_id)
    assert corr is not None
    assert corr.note == "Важный контакт"

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            await _login(client, telegram_id=80)
            saved = await client.get(f"/correspondent/{correspondent_id}")
    assert "Важный контакт" in saved.text
    assert "Заметки пока нет" not in saved.text


async def test_correspondent_update_existing_note(tmp_path) -> None:
    today = date.today()
    settings = build_settings(tmp_path)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            await _login(client, telegram_id=180)
            user_id = _current_user_id(client)
            await _seed_mail(app, user_id, [{"correspondent": "UpdateNote", "direction": "outgoing", "sent_at": today}])
            await client.get("/")
            csrf = client.cookies.get("postbox_csrf")

            async with app.state.database.session_factory() as session:
                corr = await Correspondent.find_or_create(session, owner_id=user_id, name="UpdateNote")
                correspondent_id = corr.id
                corr.note = "Old note"
                await corr.save(session)
                await session.commit()

            response = await client.post(
                f"/correspondent/{correspondent_id}/note",
                data={"csrf_token": csrf, "note": "New note"},
                follow_redirects=False,
            )

    assert response.status_code == 303
    assert response.headers["location"] == f"/correspondent/{correspondent_id}"
    async with app.router.lifespan_context(app), app.state.database.session_factory() as session:
        corr = await Correspondent.find_for_owner(session, owner_id=user_id, correspondent_id=correspondent_id)
    assert corr is not None
    assert corr.note == "New note"


async def test_correspondent_save_empty_note_sets_null(tmp_path) -> None:
    today = date.today()
    settings = build_settings(tmp_path)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            await _login(client, telegram_id=83)
            user_id = _current_user_id(client)
            await _seed_mail(app, user_id, [{"correspondent": "EmptyNote", "direction": "outgoing", "sent_at": today}])
            await client.get("/")
            csrf = client.cookies.get("postbox_csrf")

            async with app.state.database.session_factory() as session:
                corr = await Correspondent.find_or_create(session, owner_id=user_id, name="EmptyNote")
                correspondent_id = corr.id
                corr.note = "Existing"
                await corr.save(session)
                await session.commit()

            response = await client.post(
                f"/correspondent/{correspondent_id}/note",
                data={"csrf_token": csrf, "note": "   "},
                follow_redirects=False,
            )

    assert response.status_code == 303
    async with app.router.lifespan_context(app), app.state.database.session_factory() as session:
        corr = await Correspondent.find_for_owner(session, owner_id=user_id, correspondent_id=correspondent_id)
    assert corr is not None
    assert corr.note is None


async def test_correspondent_save_note_length_limit(tmp_path) -> None:
    today = date.today()
    settings = build_settings(tmp_path)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            await _login(client, telegram_id=84)
            user_id = _current_user_id(client)
            await _seed_mail(app, user_id, [{"correspondent": "Limit", "direction": "outgoing", "sent_at": today}])
            await client.get("/")
            csrf = client.cookies.get("postbox_csrf")

            async with app.state.database.session_factory() as session:
                corr = await Correspondent.find_or_create(session, owner_id=user_id, name="Limit")
                correspondent_id = corr.id

            accepted = await client.post(
                f"/correspondent/{correspondent_id}/note",
                data={"csrf_token": csrf, "note": "x" * 250},
                follow_redirects=False,
            )
            rejected = await client.post(
                f"/correspondent/{correspondent_id}/note",
                data={"csrf_token": csrf, "note": "y" * 251},
                follow_redirects=False,
            )

    assert accepted.status_code == 303
    assert rejected.status_code == 422
    assert "максимум 250" in rejected.text
    assert ("y" * 251) in rejected.text


async def test_correspondent_save_note_requires_csrf(tmp_path) -> None:
    today = date.today()
    settings = build_settings(tmp_path)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            await _login(client, telegram_id=81)
            user_id = _current_user_id(client)
            await _seed_mail(
                app,
                user_id,
                [{"correspondent": "Dave", "direction": "outgoing", "sent_at": today}],
            )

            async with app.router.lifespan_context(app), app.state.database.session_factory() as session:
                from postbox.models import Correspondent

                corr = await Correspondent.find_or_create(session, owner_id=user_id, name="Dave")
                correspondent_id = corr.id

            response = await client.post(
                f"/correspondent/{correspondent_id}/note",
                data={"csrf_token": "invalid", "note": "Test"},
                follow_redirects=False,
            )

    assert response.status_code == 303
    assert "login?error=csrf" in response.headers["location"]


async def test_correspondent_save_note_other_user_returns_404(tmp_path) -> None:
    today = date.today()
    settings = build_settings(tmp_path)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            await _login(client, telegram_id=85)
            owner_id = _current_user_id(client)
            await _seed_mail(app, owner_id, [{"correspondent": "Private", "direction": "outgoing", "sent_at": today}])
            async with app.state.database.session_factory() as session:
                corr = await Correspondent.find_or_create(session, owner_id=owner_id, name="Private")
                correspondent_id = corr.id

            await _login(client, telegram_id=86)
            await client.get("/")
            csrf = client.cookies.get("postbox_csrf")
            response = await client.post(
                f"/correspondent/{correspondent_id}/note",
                data={"csrf_token": csrf, "note": "Hacked"},
                follow_redirects=False,
            )

    assert response.status_code == 404
    async with app.router.lifespan_context(app), app.state.database.session_factory() as session:
        corr = await Correspondent.find_for_owner(session, owner_id=owner_id, correspondent_id=correspondent_id)
    assert corr is not None
    assert corr.note is None


# --- Cache-Control Headers ---------------------------------------------------
