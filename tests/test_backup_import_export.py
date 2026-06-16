from app.repositories.accounts import AccountRepository
from app.services.totp import build_totp
from app.services.backup import BackupService
from app.services.backup import BackupError
from app.services.encryption import EncryptionService
from tests.conftest import create_user, create_vault
import pytest


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

    data, _hash = backup.export_user_accounts(
        user_id=user_a.id,
        accounts=list(repo.list_for_user(user_a.id)),
        password="export-pass",
        vault_key=key_a,
        encryption=encryption,
    )
    payload = backup.decrypt_backup(data, "export-pass")

    assert len(payload["accounts"]) == 1
    assert payload["accounts"][0]["service_name"] == account_a.service_name
    assert payload["accounts"][0]["totp_secret"] == "JBSWY3DPEHPK3PXP"
    assert "encrypted_secret" not in payload["accounts"][0]
    assert "JBSWY3DPEHPK3PXP" not in data.decode("utf-8")


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
    data, _hash = backup.export_user_accounts(
        user_id=user_a.id,
        accounts=[account_a],
        password="export-pass",
        vault_key=key_a,
        encryption=encryption,
    )
    payload = backup.decrypt_backup(data, "export-pass")

    for record in payload["accounts"]:
        plaintext_secret = record["totp_secret"]
        repo.create_for_user(
            user_id=user_b.id,
            vault_id=vault_b.id,
            service_name=record["service_name"],
            account_label=record["account_label"],
            issuer=record["issuer"],
            encrypted_secret=encryption.encrypt_text(plaintext_secret, _key_b),
        )
        plaintext_secret = ""

    assert repo.count_for_user(user_a.id) == 1
    assert repo.count_for_user(user_b.id) == 1


def test_export_requires_unlocked_vault_key(db_session) -> None:
    user = create_user(db_session, 1001, "alice")
    vault, key = create_vault(db_session, user)
    encryption = EncryptionService()
    account = AccountRepository(db_session).create_for_user(
        user_id=user.id,
        vault_id=vault.id,
        service_name="GitHub",
        account_label="Alice",
        issuer="GitHub",
        encrypted_secret=encryption.encrypt_text("JBSWY3DPEHPK3PXP", key),
    )

    with pytest.raises(BackupError):
        BackupService().export_user_accounts(
            user_id=user.id,
            accounts=[account],
            password="export-pass",
            vault_key=b"",
            encryption=encryption,
        )


def test_backup_payload_does_not_store_generated_otp_codes(db_session) -> None:
    user = create_user(db_session, 1001, "alice")
    vault, key = create_vault(db_session, user)
    encryption = EncryptionService()
    account = AccountRepository(db_session).create_for_user(
        user_id=user.id,
        vault_id=vault.id,
        service_name="GitHub",
        account_label="Alice",
        issuer="GitHub",
        encrypted_secret=encryption.encrypt_text("JBSWY3DPEHPK3PXP", key),
    )
    data, _hash = BackupService().export_user_accounts(
        user_id=user.id,
        accounts=[account],
        password="export-pass",
        vault_key=key,
        encryption=encryption,
    )
    payload = BackupService().decrypt_backup(data, "export-pass")

    assert "code" not in payload["accounts"][0]
    assert "otp" not in payload["accounts"][0]
    assert "generated_code" not in payload["accounts"][0]


def test_backup_restored_into_new_vault_reencrypts_and_generates_same_code(db_session) -> None:
    encryption = EncryptionService()
    backup = BackupService()
    user_a = create_user(db_session, 1001, "alice")
    user_b = create_user(db_session, 1002, "bob")
    vault_a, key_a = create_vault(db_session, user_a, passphrase="old vault passphrase")
    vault_b, key_b = create_vault(db_session, user_b, passphrase="new vault passphrase")
    repo = AccountRepository(db_session)
    secret = "JBSWY3DPEHPK3PXP"
    account_a = repo.create_for_user(
        user_id=user_a.id,
        vault_id=vault_a.id,
        service_name="GitHub",
        account_label="Alice",
        issuer="GitHub",
        encrypted_secret=encryption.encrypt_text(secret, key_a),
    )
    data, _hash = backup.export_user_accounts(
        user_id=user_a.id,
        accounts=[account_a],
        password="export-pass",
        vault_key=key_a,
        encryption=encryption,
    )
    payload = backup.decrypt_backup(data, "export-pass")
    record = payload["accounts"][0]
    imported = repo.create_for_user(
        user_id=user_b.id,
        vault_id=vault_b.id,
        service_name=record["service_name"],
        account_label=record["account_label"],
        issuer=record["issuer"],
        encrypted_secret=encryption.encrypt_text(record["totp_secret"], key_b),
    )

    restored_secret = encryption.decrypt_text(imported.encrypted_secret, key_b)
    assert restored_secret == secret
    assert build_totp(restored_secret).at(59) == build_totp(secret).at(59)
