from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken


class EncryptionError(RuntimeError):
    pass


class EncryptionService:
    def __init__(self, master_key: str) -> None:
        self._fernet = Fernet(self._normalize_key(master_key))

    @staticmethod
    def _normalize_key(master_key: str) -> bytes:
        raw = master_key.strip().encode("utf-8")
        try:
            Fernet(raw)
            return raw
        except Exception:
            digest = hashlib.sha256(raw).digest()
            return base64.urlsafe_b64encode(digest)

    @staticmethod
    def generate_master_key() -> str:
        return Fernet.generate_key().decode("ascii")

    def encrypt_text(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")

    def decrypt_text(self, ciphertext: str) -> str:
        try:
            return self._fernet.decrypt(ciphertext.encode("ascii")).decode("utf-8")
        except (InvalidToken, UnicodeDecodeError) as exc:
            raise EncryptionError("unable to decrypt value") from exc

