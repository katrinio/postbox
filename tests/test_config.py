from pathlib import Path

import pytest

from postbox.config import ConfigurationError, Settings, WebSettings

DATABASE_URL = "postgresql+psycopg://postbox:password@localhost:5432/postbox"


def test_settings_reads_bot_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(Settings.TOKEN_VARIABLE, "secret-token")
    monkeypatch.setenv(Settings.DATABASE_URL_VARIABLE, DATABASE_URL)
    monkeypatch.setenv(Settings.LOG_LEVEL_VARIABLE, "debug")

    settings = Settings.from_env()

    assert settings.bot_token == "secret-token"
    assert settings.log_level == "DEBUG"


def test_settings_reads_dotenv_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv(Settings.TOKEN_VARIABLE, raising=False)
    monkeypatch.delenv(Settings.DATABASE_URL_VARIABLE, raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        f"POSTBOX_BOT_TOKEN=token-from-file\nPOSTBOX_DATABASE_URL={DATABASE_URL}\n",
        encoding="utf-8",
    )

    settings = Settings.from_env(env_file)

    assert settings.bot_token == "token-from-file"


def test_environment_takes_priority_over_dotenv(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv(Settings.TOKEN_VARIABLE, "token-from-environment")
    monkeypatch.setenv(Settings.DATABASE_URL_VARIABLE, DATABASE_URL)
    env_file = tmp_path / ".env"
    env_file.write_text(
        f"POSTBOX_BOT_TOKEN=token-from-file\nPOSTBOX_DATABASE_URL={DATABASE_URL}\n",
        encoding="utf-8",
    )

    settings = Settings.from_env(env_file)

    assert settings.bot_token == "token-from-environment"


def test_settings_requires_bot_token(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv(Settings.TOKEN_VARIABLE, raising=False)
    monkeypatch.setenv(Settings.DATABASE_URL_VARIABLE, DATABASE_URL)

    with pytest.raises(ConfigurationError, match=Settings.TOKEN_VARIABLE):
        Settings.from_env(tmp_path / "missing.env")


def test_settings_requires_database_url(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv(Settings.TOKEN_VARIABLE, "secret-token")
    monkeypatch.delenv(Settings.DATABASE_URL_VARIABLE, raising=False)

    with pytest.raises(ConfigurationError, match=Settings.DATABASE_URL_VARIABLE):
        Settings.from_env(tmp_path / "missing.env")


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
