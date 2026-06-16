from __future__ import annotations

import base64
import os

from argon2 import PasswordHasher, Type
from argon2.exceptions import VerifyMismatchError
from argon2.low_level import hash_secret_raw
from cryptography.fernet import Fernet, InvalidToken


class EncryptionError(RuntimeError):
    pass


class EncryptionService:
    scheme = "fernet-argon2id-v1"

    def __init__(self) -> None:
        self._hasher = PasswordHasher(type=Type.ID)

    def generate_salt(self) -> bytes:
        return os.urandom(16)

    def hash_passphrase(self, passphrase: str) -> str:
        return self._hasher.hash(passphrase)

    def verify_passphrase(self, passphrase_hash: str, passphrase: str) -> bool:
        try:
            return bool(self._hasher.verify(passphrase_hash, passphrase))
        except VerifyMismatchError:
            return False

    def derive_vault_key(self, passphrase: str, salt: bytes) -> bytes:
        raw = hash_secret_raw(
            secret=passphrase.encode("utf-8"),
            salt=salt,
            time_cost=3,
            memory_cost=65536,
            parallelism=2,
            hash_len=32,
            type=Type.ID,
        )
        return base64.urlsafe_b64encode(raw)

    def encrypt_text(self, plaintext: str, vault_key: bytes) -> bytes:
        return Fernet(vault_key).encrypt(plaintext.encode("utf-8"))

    def decrypt_text(self, ciphertext: bytes, vault_key: bytes) -> str:
        try:
            return Fernet(vault_key).decrypt(ciphertext).decode("utf-8")
        except (InvalidToken, UnicodeDecodeError) as exc:
            raise EncryptionError("unable to decrypt vault value") from exc
