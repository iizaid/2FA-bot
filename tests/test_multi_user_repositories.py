from app.repositories.accounts import AccountRepository
from app.repositories.users import UserRepository
from app.services.encryption import EncryptionService
from tests.conftest import create_user, create_vault


def test_onboarding_creates_separate_users_by_telegram_id(db_session) -> None:
    user_a = create_user(db_session, 1001, "alice")
    user_b = create_user(db_session, 1002, "bob")

    assert user_a.id != user_b.id
    assert user_a.telegram_id == 1001
    assert user_b.telegram_id == 1002


def test_user_a_cannot_list_or_search_user_b_accounts(db_session) -> None:
    encryption = EncryptionService()
    user_a = create_user(db_session, 1001, "alice")
    user_b = create_user(db_session, 1002, "bob")
    vault_a, key_a = create_vault(db_session, user_a)
    vault_b, key_b = create_vault(db_session, user_b)
    repo = AccountRepository(db_session)
    repo.create_for_user(
        user_id=user_a.id,
        vault_id=vault_a.id,
        service_name="GitHub",
        account_label="Alice",
        issuer="GitHub",
        encrypted_secret=encryption.encrypt_text("JBSWY3DPEHPK3PXP", key_a),
    )
    account_b = repo.create_for_user(
        user_id=user_b.id,
        vault_id=vault_b.id,
        service_name="Gmail",
        account_label="Bob",
        issuer="Google",
        encrypted_secret=encryption.encrypt_text("JBSWY3DPEHPK3PXP", key_b),
    )

    assert [account.service_name for account in repo.list_for_user(user_a.id)] == ["GitHub"]
    assert repo.get_for_user(user_a.id, account_b.id) is None
    assert repo.search_for_user(user_a.id, "Gmail") == []


def test_user_a_cannot_rename_or_delete_user_b_account(db_session) -> None:
    encryption = EncryptionService()
    user_a = create_user(db_session, 1001, "alice")
    user_b = create_user(db_session, 1002, "bob")
    vault_b, key_b = create_vault(db_session, user_b)
    repo = AccountRepository(db_session)
    account_b = repo.create_for_user(
        user_id=user_b.id,
        vault_id=vault_b.id,
        service_name="Gmail",
        account_label="Bob",
        issuer="Google",
        encrypted_secret=encryption.encrypt_text("JBSWY3DPEHPK3PXP", key_b),
    )

    assert repo.rename_for_user(user_a.id, account_b.id, "Changed", "Changed") is None
    assert repo.delete_for_user(user_a.id, account_b.id) is False
    assert repo.get_for_user(user_b.id, account_b.id) is not None


def test_generated_otp_codes_are_not_stored(db_session) -> None:
    encryption = EncryptionService()
    user = create_user(db_session, 1001, "alice")
    vault, key = create_vault(db_session, user)
    repo = AccountRepository(db_session)
    account = repo.create_for_user(
        user_id=user.id,
        vault_id=vault.id,
        service_name="GitHub",
        account_label="Alice",
        issuer="GitHub",
        encrypted_secret=encryption.encrypt_text("JBSWY3DPEHPK3PXP", key),
    )

    assert not hasattr(account, "code")
    assert not hasattr(account, "generated_code")


def test_blocked_and_deleted_users_are_marked_inactive(db_session) -> None:
    user = create_user(db_session, 1001, "alice")
    repo = UserRepository(db_session)

    assert repo.set_status(user.id, "blocked") is True
    assert repo.get(user.id).status == "blocked"
    assert repo.set_status(user.id, "deleted") is True
    assert repo.get(user.id).status == "deleted"
