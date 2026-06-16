from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    bot_token: str = Field(..., alias="BOT_TOKEN")
    supabase_db_url: str = Field("sqlite:///vault_dev.db", alias="SUPABASE_DB_URL")
    supabase_url: str | None = Field(None, alias="SUPABASE_URL")
    supabase_secret_key: str | None = Field(None, alias="SUPABASE_SECRET_KEY")
    admin_telegram_ids: str = Field("", alias="ADMIN_TELEGRAM_IDS")
    app_env: str = Field("development", alias="APP_ENV")
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    vault_session_seconds: int = Field(180, alias="VAULT_SESSION_SECONDS")
    code_message_ttl_seconds: int = Field(45, alias="CODE_MESSAGE_TTL_SECONDS")
    max_unlock_attempts: int = Field(5, alias="MAX_UNLOCK_ATTEMPTS")
    lockout_seconds: int = Field(300, alias="LOCKOUT_SECONDS")
    global_rate_limit_per_minute: int = Field(30, alias="GLOBAL_RATE_LIMIT_PER_MINUTE")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def database_url(self) -> str:
        return self.supabase_db_url

    @property
    def admin_ids(self) -> set[int]:
        values: set[int] = set()
        for item in self.admin_telegram_ids.split(","):
            cleaned = item.strip()
            if cleaned:
                values.add(int(cleaned))
        return values

    @field_validator(
        "vault_session_seconds",
        "code_message_ttl_seconds",
        "max_unlock_attempts",
        "lockout_seconds",
        "global_rate_limit_per_minute",
    )
    @classmethod
    def validate_positive_int(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("security and rate-limit values must be positive")
        return value

    @field_validator("supabase_db_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        allowed = (
            "postgresql://",
            "postgresql+psycopg://",
            "postgresql+psycopg2://",
            "sqlite:///",
            "sqlite:///:memory:",
        )
        if not value.startswith(allowed):
            raise ValueError("SUPABASE_DB_URL must be a PostgreSQL or local SQLite test URL")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
