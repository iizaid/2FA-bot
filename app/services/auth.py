from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from app.models import User, Vault
from app.services.encryption import EncryptionService
from app.utils.time import utc_now


@dataclass
class UnlockSession:
    user_id: str
    vault_key: bytes
    expires_at: datetime


class VaultAuthService:
    def __init__(self, encryption: EncryptionService, default_timeout_seconds: int) -> None:
        self._encryption = encryption
        self._default_timeout_seconds = default_timeout_seconds
        self._sessions: dict[str, UnlockSession] = {}

    def create_vault_material(self, passphrase: str) -> tuple[bytes, str, bytes]:
        salt = self._encryption.generate_salt()
        passphrase_hash = self._encryption.hash_passphrase(passphrase)
        vault_key = self._encryption.derive_vault_key(passphrase, salt)
        return salt, passphrase_hash, vault_key

    def unlock(self, *, user: User, vault: Vault, passphrase: str, timeout_seconds: int | None = None) -> bool:
        if not self._encryption.verify_passphrase(vault.passphrase_hash, passphrase):
            return False
        seconds = timeout_seconds or self._default_timeout_seconds
        vault_key = self._encryption.derive_vault_key(passphrase, vault.kdf_salt)
        self._sessions[user.id] = UnlockSession(
            user_id=user.id,
            vault_key=vault_key,
            expires_at=utc_now() + timedelta(seconds=seconds),
        )
        return True

    def store_session_key(self, *, user_id: str, vault_key: bytes, timeout_seconds: int | None = None) -> datetime:
        seconds = timeout_seconds or self._default_timeout_seconds
        expires_at = utc_now() + timedelta(seconds=seconds)
        self._sessions[user_id] = UnlockSession(user_id=user_id, vault_key=vault_key, expires_at=expires_at)
        return expires_at

    def lock(self, user_id: str) -> None:
        self._sessions.pop(user_id, None)

    def is_unlocked(self, user_id: str) -> bool:
        session = self._sessions.get(user_id)
        if session is None:
            return False
        if utc_now() >= session.expires_at:
            self.lock(user_id)
            return False
        return True

    def require_vault_key(self, user_id: str) -> bytes | None:
        if not self.is_unlocked(user_id):
            return None
        return self._sessions[user_id].vault_key

    def seconds_remaining(self, user_id: str) -> int:
        if not self.is_unlocked(user_id):
            return 0
        return max(0, int((self._sessions[user_id].expires_at - utc_now()).total_seconds()))
