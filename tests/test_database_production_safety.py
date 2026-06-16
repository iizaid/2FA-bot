import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from app.config import Settings
from app.db import DatabaseConfigurationError, init_db
from app.models import User


def make_settings(**overrides) -> Settings:
    values = {
        "BOT_TOKEN": "123456:ABCDEF",
        "SUPABASE_DB_URL": "sqlite:///:memory:",
        "APP_ENV": "test",
        "AUTO_CREATE_TABLES": False,
    }
    values.update(overrides)
    return Settings(**values)


def test_production_mode_does_not_call_create_all(monkeypatch) -> None:
    def fail_create_all(_engine):
        raise AssertionError("create_all should not run in production by default")

    monkeypatch.setattr("app.models.Base.metadata.create_all", fail_create_all)

    init_db(make_settings(APP_ENV="production", AUTO_CREATE_TABLES=False))


def test_production_mode_rejects_auto_create_tables_true() -> None:
    with pytest.raises(DatabaseConfigurationError):
        init_db(make_settings(APP_ENV="production", AUTO_CREATE_TABLES=True))


def test_uuid_columns_compile_to_postgresql_uuid() -> None:
    ddl = str(CreateTable(User.__table__).compile(dialect=postgresql.dialect())).lower()

    assert "id uuid not null" in ddl
    assert "telegram_id bigint not null" in ddl
