from pathlib import Path

import pytest

from postbox.config import ConfigurationError, WebSettings

DATABASE_URL = "postgresql+psycopg://postbox:password@localhost:5432/postbox"


def test_web_settings_requires_database_url(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv(WebSettings.DATABASE_URL_VARIABLE, raising=False)
    monkeypatch.setenv(WebSettings.JWT_SECRET_KEY_VARIABLE, "secret-key")

    with pytest.raises(ConfigurationError, match=WebSettings.DATABASE_URL_VARIABLE):
        WebSettings.from_env(tmp_path / "missing.env")


def test_web_settings_requires_jwt_secret_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv(WebSettings.DATABASE_URL_VARIABLE, DATABASE_URL)
    monkeypatch.delenv(WebSettings.JWT_SECRET_KEY_VARIABLE, raising=False)

    with pytest.raises(ConfigurationError, match=WebSettings.JWT_SECRET_KEY_VARIABLE):
        WebSettings.from_env(tmp_path / "missing.env")


def test_web_settings_reads_registration_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(WebSettings.DATABASE_URL_VARIABLE, DATABASE_URL)
    monkeypatch.setenv(WebSettings.JWT_SECRET_KEY_VARIABLE, "secret-key")
    monkeypatch.setenv(WebSettings.REGISTRATION_LIMIT_VARIABLE, "10")

    settings = WebSettings.from_env()

    assert settings.database_url == DATABASE_URL
    assert settings.registration_limit == 10


def test_web_settings_defaults_registration_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(WebSettings.DATABASE_URL_VARIABLE, DATABASE_URL)
    monkeypatch.setenv(WebSettings.JWT_SECRET_KEY_VARIABLE, "secret-key")
    monkeypatch.delenv(WebSettings.REGISTRATION_LIMIT_VARIABLE, raising=False)

    settings = WebSettings.from_env()

    assert settings.registration_limit == 5


def test_web_settings_reads_auth_integration_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(WebSettings.DATABASE_URL_VARIABLE, DATABASE_URL)
    monkeypatch.setenv(WebSettings.JWT_SECRET_KEY_VARIABLE, "secret-key")
    monkeypatch.setenv(WebSettings.HUB_BOT_URL_VARIABLE, "https://t.me/hub")

    settings = WebSettings.from_env()

    assert settings.hub_bot_url == "https://t.me/hub"
