import logging
from pathlib import Path

from app.logging_config import SecretRedactionFilter


def test_sensitive_words_are_redacted_from_logs() -> None:
    record = logging.LogRecord("test", logging.INFO, __file__, 1, "otpauth://totp/example secret password", (), None)
    SecretRedactionFilter().filter(record)
    assert record.msg == "[sensitive log message redacted]"


def test_rls_migration_files_exist_and_enable_rls() -> None:
    migration = Path("app/db_migrations/002_rls_policies.sql")
    text = migration.read_text(encoding="utf-8").lower()
    assert "enable row level security" in text
    assert "vault_accounts" in text
