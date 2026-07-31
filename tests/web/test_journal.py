"""Tests for Tests for journal/mailbox viewing and filtering.."""

from __future__ import annotations

from datetime import date, timedelta

import httpx

from postbox.api import create_app
from postbox.models import Correspondent

from .conftest import (
    JWT_SECRET,
    _current_user_id,
    _has_nested_anchor,
    _login,
    _seed_mail,
    app_client,
    build_settings,
)


async def test_unauthenticated_journal_redirects(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        response = await client.get("/")
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


async def test_authenticated_journal_returns_html(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        await _login(client)
        response = await client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Журнал" in response.text


async def test_journal_renders_mail_items(tmp_path) -> None:
    today = date.today()
    settings = build_settings(tmp_path)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            await _login(client, telegram_id=10, first_name="Katrin")
            # Need user id — read it from the JWT
            from postbox.auth import decode_jwt_token

            token = client.cookies.get("postbox_session")
            user_id = decode_jwt_token(token, JWT_SECRET)["user_id"]

            await _seed_mail(
                app,
                user_id,
                [
                    {"correspondent": "Маша", "direction": "outgoing", "sent_at": today - timedelta(days=5)},
                    {
                        "correspondent": "Аня",
                        "direction": "incoming",
                        "received_at": today - timedelta(days=2),
                        "sent_at": today - timedelta(days=10),
                    },
                ],
            )

            response = await client.get("/")

    assert response.status_code == 200
    assert "Маша" in response.text
    assert "Аня" in response.text
    assert "Отправлено" in response.text
    assert "Получено" in response.text
    assert "Исходящее" not in response.text
    assert "Входящее" not in response.text


async def test_journal_items_are_sorted_and_have_separate_links(tmp_path) -> None:
    today = date.today()
    settings = build_settings(tmp_path)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            await _login(client, telegram_id=11)
            user_id = _current_user_id(client)
            await _seed_mail(
                app,
                user_id,
                [
                    {
                        "correspondent": "Older Route",
                        "direction": "outgoing",
                        "sent_at": today - timedelta(days=7),
                        "origin_city": "Very Long Origin City Name",
                        "destination_city": "Very Long Destination City Name",
                        "note": "Has note",
                    },
                    {"correspondent": "Newest Person", "direction": "incoming", "received_at": today},
                ],
            )

            response = await client.get("/")

    assert response.status_code == 200
    assert response.text.index("Newest Person") < response.text.index("Older Route")
    assert 'class="journal-row__link" href="/mail/' in response.text
    assert 'class="journal-row__name" href="/correspondent/' not in response.text
    assert '<a class="journal-row"' not in response.text
    assert "Получено · <time" in response.text
    assert "Отправлено · <time" in response.text
    assert "Исходящее" not in response.text
    assert "Входящее" not in response.text
    assert not _has_nested_anchor(response.text)


async def test_journal_filters_and_pagination_keep_working(tmp_path) -> None:
    today = date.today()
    settings = build_settings(tmp_path)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            await _login(client, telegram_id=12)
            user_id = _current_user_id(client)
            await _seed_mail(
                app,
                user_id,
                [
                    *[
                        {
                            "correspondent": "Filtered Person",
                            "direction": "incoming",
                            "received_at": today - timedelta(days=index),
                            "origin_country_code": "DE",
                        }
                        for index in range(52)
                    ],
                    {
                        "correspondent": "Out Only",
                        "direction": "outgoing",
                        "sent_at": today,
                        "origin_country_code": "FR",
                    },
                ],
            )

            async with app.state.database.session_factory() as session:
                corr = await Correspondent.find_or_create(session, owner_id=user_id, name="Filtered Person")
                correspondent_id = corr.id

            page_two = await client.get(f"/?filter=incoming&country=DE&correspondent_id={correspondent_id}&page=2")

    assert page_two.status_code == 200
    assert "Получено" in page_two.text
    assert "Отправлено · <time" not in page_two.text
    assert f'href="/?filter=all&amp;correspondent_id={correspondent_id}&amp;country=DE"' in page_two.text
    previous_page_link = f'href="/?filter=incoming&amp;correspondent_id={correspondent_id}&amp;country=DE&amp;page=1"'
    assert previous_page_link in page_two.text
    assert 'href="/?filter=incoming&amp;page=3"' not in page_two.text


async def test_journal_empty_state(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        await _login(client, telegram_id=20, first_name="Empty")
        response = await client.get("/")
    assert response.status_code == 200
    assert "Журнал пока пуст" in response.text
    assert "Добавить письмо" in response.text


async def test_journal_invalid_filter_defaults_to_all(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        await _login(client, telegram_id=31)
        response = await client.get("/?filter=bogus")
    assert response.status_code == 200


async def test_journal_renders_geography_compactly(tmp_path) -> None:
    today = date.today()
    settings = build_settings(tmp_path)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            await _login(client, telegram_id=32)
            user_id = _current_user_id(client)
            await _seed_mail(
                app,
                user_id,
                [
                    {
                        "correspondent": "FullRoute",
                        "direction": "outgoing",
                        "sent_at": today,
                        "origin_city": "Berlin",
                        "origin_country_code": "DE",
                        "destination_city": "Paris",
                        "destination_country_code": "FR",
                    },
                    {
                        "correspondent": "PartialRoute",
                        "direction": "incoming",
                        "received_at": today,
                        "origin_country_code": "CZ",
                        "destination_city": "Rome",
                    },
                    {"correspondent": "NoRoute", "direction": "outgoing", "sent_at": today},
                ],
            )
            response = await client.get("/")

    assert response.status_code == 200
    assert "Berlin, DE -&gt; Paris, FR" in response.text
    assert "CZ -&gt; Rome" in response.text
    assert "NoRoute" in response.text
    assert 'href="/mail/' in response.text
    assert "/correspondent/" not in response.text


async def test_journal_escapes_city_geography(tmp_path) -> None:
    settings = build_settings(tmp_path)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            await _login(client, telegram_id=33)
            user_id = _current_user_id(client)
            await _seed_mail(
                app,
                user_id,
                [
                    {
                        "correspondent": "Escaped",
                        "direction": "outgoing",
                        "sent_at": date.today(),
                        "origin_city": '<script>alert("x")</script>',
                    }
                ],
            )
            response = await client.get("/")

    assert '<script>alert("x")</script>' not in response.text
    assert "&lt;script&gt;" in response.text


async def test_journal_country_filter_matches_either_route_end_and_stays_private(tmp_path) -> None:
    today = date.today()
    settings = build_settings(tmp_path)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            await _login(client, telegram_id=34, first_name="Owner")
            owner_id = _current_user_id(client)
            await _seed_mail(
                app,
                owner_id,
                [
                    {
                        "correspondent": "BerlinOutgoing",
                        "direction": "outgoing",
                        "sent_at": today,
                        "origin_city": "Berlin",
                        "origin_country_code": "DE",
                        "destination_city": "Paris",
                        "destination_country_code": "FR",
                    },
                    {
                        "correspondent": "RomeIncoming",
                        "direction": "incoming",
                        "received_at": today,
                        "origin_city": "Rome",
                        "origin_country_code": "IT",
                        "destination_city": "Berlin",
                        "destination_country_code": "DE",
                    },
                    {
                        "correspondent": "PragueOnly",
                        "direction": "outgoing",
                        "sent_at": today,
                        "origin_country_code": "CZ",
                    },
                ],
            )
            await _login(client, telegram_id=35, first_name="Other")
            other_id = _current_user_id(client)
            await _seed_mail(
                app,
                other_id,
                [
                    {
                        "correspondent": "PrivateParis",
                        "direction": "outgoing",
                        "sent_at": today,
                        "origin_city": "Berlin",
                        "origin_country_code": "JP",
                        "destination_city": "Paris",
                        "destination_country_code": "JP",
                    }
                ],
            )
            await _login(client, telegram_id=34, first_name="Owner")

            de_country = await client.get("/?country=de")
            fr_country = await client.get("/?country=fr")
            unknown_country = await client.get("/?country=JP")
            invalid = await client.get("/?country=bad")

    assert "BerlinOutgoing" in de_country.text
    assert "RomeIncoming" in de_country.text
    assert ">PragueOnly</a>" not in de_country.text
    assert "BerlinOutgoing" in fr_country.text
    assert ">RomeIncoming</a>" not in fr_country.text
    assert ">PrivateParis</a>" not in de_country.text
    assert ">JP<" not in de_country.text
    assert ">PrivateParis</a>" not in unknown_country.text
    assert unknown_country.status_code == 200
    assert invalid.status_code == 200
    assert de_country.status_code == 200


async def test_journal_other_user_data_not_visible(tmp_path) -> None:
    today = date.today()
    settings = build_settings(tmp_path)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            # User A creates data
            await _login(client, telegram_id=40, first_name="Alice")
            from postbox.auth import decode_jwt_token

            token_a = client.cookies.get("postbox_session")
            uid_a = decode_jwt_token(token_a, JWT_SECRET)["user_id"]
            await _seed_mail(
                app,
                uid_a,
                [
                    {"correspondent": "SecretPerson", "direction": "outgoing", "sent_at": today},
                ],
            )

            # User B logs in
            await _login(client, telegram_id=41, first_name="Bob")
            response = await client.get("/")

    assert response.status_code == 200
    assert "SecretPerson" not in response.text


async def test_journal_shows_navigation(tmp_path) -> None:
    async with app_client(build_settings(tmp_path)) as client:
        await _login(client, telegram_id=50)
        response = await client.get("/")
    assert response.status_code == 200
    assert "Postbox" in response.text
    assert "Выйти" in response.text


# --- Phase 3: routing / proxy ------------------------------------------------
