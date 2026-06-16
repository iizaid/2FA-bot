import pytest

from app.services.admin import AdminSafetyError, AdminService
from app.services.auth import VaultAuthService
from app.services.encryption import EncryptionService
from app.services.rate_limit import RateLimitService
from tests.conftest import create_user, create_vault


def test_admin_cannot_decrypt_or_generate_user_codes() -> None:
    admin = AdminService()
    with pytest.raises(AdminSafetyError):
        admin.decrypt_user_secret()
    with pytest.raises(AdminSafetyError):
        admin.generate_user_code()


def test_wrong_passphrase_cannot_unlock_vault(db_session) -> None:
    user = create_user(db_session, 1001, "alice")
    vault, _key = create_vault(db_session, user, passphrase="right-passphrase")
    encryption = EncryptionService()
    auth = VaultAuthService(encryption, 180)

    assert auth.unlock(user=user, vault=vault, passphrase="wrong-passphrase") is False


def test_lockout_works_after_too_many_failed_attempts() -> None:
    limiter = RateLimitService(max_unlock_attempts=2, lockout_seconds=300)
    limiter.register_unlock_failure("user-1")
    assert limiter.unlock_is_locked("user-1") is False
    limiter.register_unlock_failure("user-1")
    assert limiter.unlock_is_locked("user-1") is True
