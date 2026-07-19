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
    jwt_secret_key: str
    log_level: str = "INFO"
    registration_limit: int = 5

    DATABASE_URL_VARIABLE: ClassVar[str] = "POSTBOX_DATABASE_URL"
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
        )
