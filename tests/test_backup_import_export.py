import base64

from app.repositories.accounts import AccountRepository
from app.services.backup import BackupService
from app.services.encryption import EncryptionService
from tests.conftest import create_user, create_vault


def test_export_exports_only_current_user_accounts(db_session) -> None:
    encryption = EncryptionService()
    backup = BackupService()
    user_a = create_user(db_session, 1001, "alice")
    user_b = create_user(db_session, 1002, "bob")
    vault_a, key_a = create_vault(db_session, user_a)
    vault_b, key_b = create_vault(db_session, user_b)
    repo = AccountRepository(db_session)
    account_a = repo.create_for_user(
        user_id=user_a.id,
        vault_id=vault_a.id,
        service_name="GitHub",
        account_label="Alice",
        issuer="GitHub",
        encrypted_secret=encryption.encrypt_text("JBSWY3DPEHPK3PXP", key_a),
    )
    repo.create_for_user(
        user_id=user_b.id,
        vault_id=vault_b.id,
        service_name="Gmail",
        account_label="Bob",
        issuer="Google",
        encrypted_secret=encryption.encrypt_text("JBSWY3DPEHPK3PXP", key_b),
    )

    data, _hash = backup.export_user_accounts(user_id=user_a.id, accounts=list(repo.list_for_user(user_a.id)), password="export-pass")
    payload = backup.decrypt_backup(data, "export-pass")

    assert len(payload["accounts"]) == 1
    assert payload["accounts"][0]["service_name"] == account_a.service_name


def test_import_imports_only_into_current_user_vault(db_session) -> None:
    encryption = EncryptionService()
    backup = BackupService()
    user_a = create_user(db_session, 1001, "alice")
    user_b = create_user(db_session, 1002, "bob")
    vault_a, key_a = create_vault(db_session, user_a)
    vault_b, _key_b = create_vault(db_session, user_b)
    repo = AccountRepository(db_session)
    account_a = repo.create_for_user(
        user_id=user_a.id,
        vault_id=vault_a.id,
        service_name="GitHub",
        account_label="Alice",
        issuer="GitHub",
        encrypted_secret=encryption.encrypt_text("JBSWY3DPEHPK3PXP", key_a),
    )
    data, _hash = backup.export_user_accounts(user_id=user_a.id, accounts=[account_a], password="export-pass")
    payload = backup.decrypt_backup(data, "export-pass")

    for record in payload["accounts"]:
        repo.create_for_user(
            user_id=user_b.id,
            vault_id=vault_b.id,
            service_name=record["service_name"],
            account_label=record["account_label"],
            issuer=record["issuer"],
            encrypted_secret=base64.b64decode(record["encrypted_secret"]),
        )

    assert repo.count_for_user(user_a.id) == 1
    assert repo.count_for_user(user_b.id) == 1
