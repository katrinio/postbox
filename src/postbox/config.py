import os
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from dotenv import load_dotenv


class ConfigurationError(RuntimeError):
    """Raised when Postbox cannot start with the current environment."""


def _env_bool(name: str, *, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


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
    """Settings for the web application (HTTP transport + Telegram login)."""

    database_url: str
    jwt_secret_key: str
    log_level: str = "INFO"
    registration_limit: int = 5
    # Telegram Login Widget: bot token verifies the signed login payload; the
    # username renders the widget. Both come from BotFather.
    bot_token: str | None = None
    bot_username: str | None = None
    # Session cookie: Secure is on by default and only disabled for local dev/test.
    cookie_secure: bool = True
    # Dev login: when true, a password-less dev login form is accepted. Off by
    # default so production never bypasses Telegram signature verification.
    dev_login: bool = False

    DATABASE_URL_VARIABLE: ClassVar[str] = "POSTBOX_DATABASE_URL"
    JWT_SECRET_KEY_VARIABLE: ClassVar[str] = "POSTBOX_JWT_SECRET_KEY"
    LOG_LEVEL_VARIABLE: ClassVar[str] = "POSTBOX_LOG_LEVEL"
    REGISTRATION_LIMIT_VARIABLE: ClassVar[str] = "POSTBOX_REGISTRATION_LIMIT"
    BOT_TOKEN_VARIABLE: ClassVar[str] = "POSTBOX_BOT_TOKEN"
    BOT_USERNAME_VARIABLE: ClassVar[str] = "POSTBOX_BOT_USERNAME"
    COOKIE_SECURE_VARIABLE: ClassVar[str] = "POSTBOX_COOKIE_SECURE"
    DEV_LOGIN_VARIABLE: ClassVar[str] = "POSTBOX_DEV_LOGIN"

    @classmethod
    def from_env(cls, env_file: str | Path = ".env") -> WebSettings:
        load_dotenv(dotenv_path=env_file, override=False)

        database_url = os.getenv(cls.DATABASE_URL_VARIABLE, "").strip()
        if not database_url:
            message = f"{cls.DATABASE_URL_VARIABLE} is required"
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
            jwt_secret_key=jwt_secret,
            log_level=log_level,
            registration_limit=registration_limit,
            bot_token=os.getenv(cls.BOT_TOKEN_VARIABLE, "").strip() or None,
            bot_username=os.getenv(cls.BOT_USERNAME_VARIABLE, "").strip() or None,
            cookie_secure=_env_bool(cls.COOKIE_SECURE_VARIABLE, default=True),
            dev_login=_env_bool(cls.DEV_LOGIN_VARIABLE, default=False),
        )
