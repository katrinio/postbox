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
    bot_token: str
    jwt_secret_key: str
    log_level: str = "INFO"
    registration_limit: int = 5

    DATABASE_URL_VARIABLE: ClassVar[str] = "POSTBOX_DATABASE_URL"
    OWNER_TELEGRAM_ID_VARIABLE: ClassVar[str] = "POSTBOX_WEB_OWNER_TELEGRAM_ID"
    BOT_TOKEN_VARIABLE: ClassVar[str] = "POSTBOX_BOT_TOKEN"
    JWT_SECRET_KEY_VARIABLE: ClassVar[str] = "POSTBOX_JWT_SECRET_KEY"
    LOG_LEVEL_VARIABLE: ClassVar[str] = "POSTBOX_LOG_LEVEL"
    REGISTRATION_LIMIT_VARIABLE: ClassVar[str] = "POSTBOX_REGISTRATION_LIMIT"

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

        bot_token = os.getenv(cls.BOT_TOKEN_VARIABLE, "").strip()
        if not bot_token:
            message = f"{cls.BOT_TOKEN_VARIABLE} is required"
            raise ConfigurationError(message)

        jwt_secret = os.getenv(cls.JWT_SECRET_KEY_VARIABLE, "").strip()
        if not jwt_secret:
            message = f"{cls.JWT_SECRET_KEY_VARIABLE} is required"
            raise ConfigurationError(message)

        log_level = os.getenv(cls.LOG_LEVEL_VARIABLE, "INFO").strip().upper() or "INFO"
        registration_limit_str = os.getenv(cls.REGISTRATION_LIMIT_VARIABLE, "5").strip()
        try:
            registration_limit = int(registration_limit_str)
        except ValueError:
            registration_limit = 5

        return cls(
            database_url=database_url,
            owner_telegram_id=owner_telegram_id,
            bot_token=bot_token,
            jwt_secret_key=jwt_secret,
            log_level=log_level,
            registration_limit=registration_limit,
        )
