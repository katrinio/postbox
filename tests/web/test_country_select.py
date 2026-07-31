"""Tests for Tests for country selection and geography validation.."""

from __future__ import annotations

from datetime import date

import httpx
import pytest

from postbox.api import create_app
from postbox.models import MailItem, MailJournalFilter

from .conftest import (
    _current_user_id,
    _login,
    build_settings,
)


async def test_normalize_country_code_with_valid_iso_codes() -> None:
    """normalize_country_code should accept valid ISO 3166-1 alpha-2 codes."""
    # Test some standard codes
    assert MailItem.normalize_country_code("DE") == "DE"
    assert MailItem.normalize_country_code("FR") == "FR"
    assert MailItem.normalize_country_code("us") == "US"  # lowercase -> uppercase
    assert MailItem.normalize_country_code("JP") == "JP"
    assert MailItem.normalize_country_code("CZ") == "CZ"
    assert MailItem.normalize_country_code("IT") == "IT"


async def test_normalize_country_code_rejects_invalid_codes() -> None:
    """normalize_country_code should reject codes not in pycountry."""
    from postbox.models import MailGeographyError

    with pytest.raises(MailGeographyError, match="not a valid ISO 3166-1 alpha-2 code"):
        MailItem.normalize_country_code("XX")

    with pytest.raises(MailGeographyError, match="not a valid ISO 3166-1 alpha-2 code"):
        MailItem.normalize_country_code("ZZ")


async def test_normalize_country_code_rejects_format_errors() -> None:
    """normalize_country_code should reject codes that aren't 2 ASCII letters."""
    from postbox.models import MailGeographyError

    with pytest.raises(MailGeographyError, match="exactly 2 ASCII letters"):
        MailItem.normalize_country_code("D")  # 1 letter

    with pytest.raises(MailGeographyError, match="exactly 2 ASCII letters"):
        MailItem.normalize_country_code("DEU")  # 3 letters

    with pytest.raises(MailGeographyError, match="exactly 2 ASCII letters"):
        MailItem.normalize_country_code("D1")  # contains digit


async def test_new_mail_form_includes_countries_list(tmp_path) -> None:
    """New mail form should include countries_list in context."""
    settings = build_settings(tmp_path)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            await _login(client)
            response = await client.get("/mail/new")
            assert response.status_code == 200
            html = response.text
            # Check that countries list is embedded in script
            assert "countriesData" in html
            assert '"code":"DE"' in html or '"code": "DE"' in html
            assert '"code":"FR"' in html or '"code": "FR"' in html
            # Check that input fields are present
            assert 'id="origin_country_display"' in html
            assert 'id="destination_country_display"' in html
            # Check that hidden inputs are present
            assert 'id="origin_country"' in html and 'type="hidden"' in html
            assert 'id="destination_country"' in html and 'type="hidden"' in html
            # Check that dropdown divs are present
            assert 'data-dropdown="origin_country"' in html
            assert 'data-dropdown="destination_country"' in html


async def test_mail_form_validation_with_invalid_country_code(tmp_path) -> None:
    """Submitting form with invalid country code should return 422."""
    settings = build_settings(tmp_path)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            await _login(client)
            # Get form to set CSRF cookie
            await client.get("/mail/new")
            csrf = client.cookies.get("postbox_csrf")
            response = await client.post(
                "/mail",
                data={
                    "csrf_token": csrf,
                    "direction": "outgoing",
                    "correspondent": "Test Person",
                    "mail_date": str(date.today()),
                    "origin_country": "XX",  # Invalid code
                    "origin_city": "",
                    "destination_country": "",
                    "destination_city": "",
                    "note": "",
                },
            )
            assert response.status_code == 422
            assert "not a valid ISO 3166-1 alpha-2 code" in response.text


async def test_mail_form_validation_with_valid_country_codes(tmp_path) -> None:
    """Submitting form with valid country codes should succeed."""
    today = date.today()
    settings = build_settings(tmp_path)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            await _login(client)
            user_id = _current_user_id(client)
            # Get form to set CSRF cookie
            await client.get("/mail/new")
            csrf = client.cookies.get("postbox_csrf")
            response = await client.post(
                "/mail",
                data={
                    "csrf_token": csrf,
                    "direction": "outgoing",
                    "correspondent": "Test Person",
                    "mail_date": str(today),
                    "origin_country": "DE",
                    "origin_city": "Berlin",
                    "destination_country": "FR",
                    "destination_city": "Paris",
                    "note": "",
                },
            )
            assert response.status_code == 303
            # Verify that mail was created with correct country codes
            async with app.state.database.session_factory() as session:
                journal_page = await MailItem.journal_page(
                    session, user_id, view=MailJournalFilter.ALL, page=1, page_size=10
                )
                assert len(journal_page.items) > 0
                assert journal_page.items[0].origin_country_code == "DE"
                assert journal_page.items[0].destination_country_code == "FR"
