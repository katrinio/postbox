import os
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from dotenv import load_dotenv


class ConfigurationError(RuntimeError):
    """Raised when Postbox cannot start with the current environment."""


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings loaded from environment variables."""

    bot_token: str
    database_url: str
    log_level: str = "INFO"

    TOKEN_VARIABLE: ClassVar[str] = "POSTBOX_BOT_TOKEN"
    DATABASE_URL_VARIABLE: ClassVar[str] = "POSTBOX_DATABASE_URL"
    LOG_LEVEL_VARIABLE: ClassVar[str] = "POSTBOX_LOG_LEVEL"

    @classmethod
    def from_env(cls, env_file: str | Path = ".env") -> Settings:
        load_dotenv(dotenv_path=env_file, override=False)

        token = os.getenv(cls.TOKEN_VARIABLE, "").strip()
        if not token:
            message = f"{cls.TOKEN_VARIABLE} is required"
            raise ConfigurationError(message)

        database_url = os.getenv(cls.DATABASE_URL_VARIABLE, "").strip()
        if not database_url:
            message = f"{cls.DATABASE_URL_VARIABLE} is required"
            raise ConfigurationError(message)

        log_level = os.getenv(cls.LOG_LEVEL_VARIABLE, "INFO").strip().upper() or "INFO"
        return cls(bot_token=token, database_url=database_url, log_level=log_level)


@dataclass(frozen=True, slots=True)
class WebSettings:
    """Settings for the local web API until account authentication is added."""

    database_url: str
    owner_telegram_id: int
    log_level: str = "INFO"

    DATABASE_URL_VARIABLE: ClassVar[str] = "POSTBOX_DATABASE_URL"
    OWNER_TELEGRAM_ID_VARIABLE: ClassVar[str] = "POSTBOX_WEB_OWNER_TELEGRAM_ID"
    LOG_LEVEL_VARIABLE: ClassVar[str] = "POSTBOX_LOG_LEVEL"

    @classmethod
    def from_env(cls, env_file: str | Path = ".env") -> WebSettings:
        load_dotenv(dotenv_path=env_file, override=False)

        database_url = os.getenv(cls.DATABASE_URL_VARIABLE, "").strip()
        if not database_url:
            message = f"{cls.DATABASE_URL_VARIABLE} is required"
            raise ConfigurationError(message)

        owner_value = os.getenv(cls.OWNER_TELEGRAM_ID_VARIABLE, "").strip()
        if not owner_value:
            message = f"{cls.OWNER_TELEGRAM_ID_VARIABLE} is required"
            raise ConfigurationError(message)
        try:
            owner_telegram_id = int(owner_value)
        except ValueError:
            message = f"{cls.OWNER_TELEGRAM_ID_VARIABLE} must be an integer"
            raise ConfigurationError(message) from None
        if owner_telegram_id <= 0:
            message = f"{cls.OWNER_TELEGRAM_ID_VARIABLE} must be positive"
            raise ConfigurationError(message)

        log_level = os.getenv(cls.LOG_LEVEL_VARIABLE, "INFO").strip().upper() or "INFO"
        return cls(
            database_url=database_url,
            owner_telegram_id=owner_telegram_id,
            log_level=log_level,
        )
