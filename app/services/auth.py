from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.utils.time import utc_now


@dataclass
class UnlockSession:
    expires_at: datetime


class VaultAuthService:
    def __init__(self, default_timeout_seconds: int) -> None:
        self._hasher = PasswordHasher()
        self._session: UnlockSession | None = None
        self._default_timeout_seconds = default_timeout_seconds

    def hash_pin(self, pin: str) -> str:
        return self._hasher.hash(pin)

    def verify_pin(self, pin_hash: str, pin: str) -> bool:
        try:
            return bool(self._hasher.verify(pin_hash, pin))
        except VerifyMismatchError:
            return False

    def unlock(self, timeout_seconds: int | None = None) -> None:
        seconds = timeout_seconds or self._default_timeout_seconds
        self._session = UnlockSession(expires_at=utc_now() + timedelta(seconds=seconds))

    def lock(self) -> None:
        self._session = None

    def is_unlocked(self) -> bool:
        if self._session is None:
            return False
        if utc_now() >= self._session.expires_at:
            self.lock()
            return False
        return True

    def seconds_remaining(self) -> int:
        if not self.is_unlocked() or self._session is None:
            return 0
        return max(0, int((self._session.expires_at - utc_now()).total_seconds()))

