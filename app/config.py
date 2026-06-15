from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    bot_token: str = Field(..., alias="BOT_TOKEN")
    owner_telegram_id: int = Field(..., alias="OWNER_TELEGRAM_ID")
    vault_master_key: str = Field(..., alias="VAULT_MASTER_KEY")
    database_url: str = Field("sqlite:///vault.db", alias="DATABASE_URL")
    vault_session_seconds: int = Field(180, alias="VAULT_SESSION_SECONDS")
    code_message_ttl_seconds: int = Field(45, alias="CODE_MESSAGE_TTL_SECONDS")
    log_level: str = Field("INFO", alias="LOG_LEVEL")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("vault_session_seconds", "code_message_ttl_seconds")
    @classmethod
    def validate_positive_seconds(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("timeout values must be positive")
        return value

    @field_validator("database_url")
    @classmethod
    def validate_sqlite_default(cls, value: str) -> str:
        if not value.startswith("sqlite:///") and value != "sqlite:///:memory:":
            raise ValueError("only sqlite database URLs are supported by this personal bot")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()

