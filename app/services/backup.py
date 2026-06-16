from __future__ import annotations

import base64
import hashlib
import json
import os
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.models import VaultAccount
from app.services.encryption import EncryptionService
from app.utils.time import utc_now


class BackupError(RuntimeError):
    pass


class BackupService:
    iterations = 1_200_000

    def _derive_key(self, password: str, salt: bytes) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=self.iterations,
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))

    def export_user_accounts(
        self,
        *,
        user_id: str,
        accounts: list[VaultAccount],
        password: str,
        vault_key: bytes,
        encryption: EncryptionService,
    ) -> tuple[bytes, str]:
        if not vault_key:
            raise BackupError("vault must be unlocked before export")
        salt = os.urandom(16)
        fernet = Fernet(self._derive_key(password, salt))
        exported_accounts = []
        for account in accounts:
            if account.user_id != user_id:
                continue
            totp_secret = encryption.decrypt_text(account.encrypted_secret, vault_key)
            exported_accounts.append(
                {
                    "service_name": account.service_name,
                    "account_label": account.account_label,
                    "issuer": account.issuer,
                    "totp_secret": totp_secret,
                    "encrypted_metadata": account.encrypted_metadata,
                    "algorithm": account.algorithm,
                    "digits": account.digits,
                    "period": account.period,
                }
            )
            totp_secret = ""
        payload = {
            "version": 1,
            "exported_at": utc_now().isoformat(),
            "accounts": exported_accounts,
        }
        token = fernet.encrypt(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
        exported_accounts.clear()
        payload.clear()
        wrapper = {
            "format": "totp-vault-bot-backup",
            "version": 1,
            "kdf": "PBKDF2HMAC-SHA256",
            "iterations": self.iterations,
            "salt": base64.b64encode(salt).decode("ascii"),
            "payload": token.decode("ascii"),
        }
        data = json.dumps(wrapper, indent=2).encode("utf-8")
        password = ""
        return data, hashlib.sha256(data).hexdigest()

    def decrypt_backup(self, backup_bytes: bytes, password: str) -> dict[str, Any]:
        try:
            wrapper = json.loads(backup_bytes.decode("utf-8"))
            if wrapper.get("format") != "totp-vault-bot-backup":
                raise BackupError("unsupported backup format")
            salt = base64.b64decode(wrapper["salt"])
            token = wrapper["payload"].encode("ascii")
            fernet = Fernet(self._derive_key(password, salt))
            payload = json.loads(fernet.decrypt(token).decode("utf-8"))
        except (KeyError, ValueError, InvalidToken, json.JSONDecodeError) as exc:
            raise BackupError("backup could not be decrypted or parsed") from exc
        if payload.get("version") != 1 or not isinstance(payload.get("accounts"), list):
            raise BackupError("unsupported backup payload")
        return payload
