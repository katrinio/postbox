from pathlib import Path

import pytest

from postbox.config import ConfigurationError, Settings


def test_settings_reads_bot_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(Settings.TOKEN_VARIABLE, "secret-token")
    monkeypatch.setenv(Settings.LOG_LEVEL_VARIABLE, "debug")

    settings = Settings.from_env()

    assert settings.bot_token == "secret-token"
    assert settings.log_level == "DEBUG"


def test_settings_reads_dotenv_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv(Settings.TOKEN_VARIABLE, raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("POSTBOX_BOT_TOKEN=token-from-file\n", encoding="utf-8")

    settings = Settings.from_env(env_file)

    assert settings.bot_token == "token-from-file"


def test_environment_takes_priority_over_dotenv(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv(Settings.TOKEN_VARIABLE, "token-from-environment")
    env_file = tmp_path / ".env"
    env_file.write_text("POSTBOX_BOT_TOKEN=token-from-file\n", encoding="utf-8")

    settings = Settings.from_env(env_file)

    assert settings.bot_token == "token-from-environment"


def test_settings_requires_bot_token(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv(Settings.TOKEN_VARIABLE, raising=False)

    with pytest.raises(ConfigurationError, match=Settings.TOKEN_VARIABLE):
        Settings.from_env(tmp_path / "missing.env")
