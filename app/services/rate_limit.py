from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from app.utils.time import utc_now


@dataclass
class AttemptState:
    failed_count: int = 0
    locked_until: datetime | None = None


class UnlockRateLimiter:
    def __init__(self, *, max_attempts: int = 5, lock_seconds: int = 300) -> None:
        self.max_attempts = max_attempts
        self.lock_seconds = lock_seconds
        self._state = AttemptState()

    def is_locked(self) -> bool:
        locked_until = self._state.locked_until
        if locked_until is None:
            return False
        if utc_now() >= locked_until:
            self._state = AttemptState()
            return False
        return True

    def seconds_remaining(self) -> int:
        if not self.is_locked() or self._state.locked_until is None:
            return 0
        return max(0, int((self._state.locked_until - utc_now()).total_seconds()))

    def register_failure(self) -> None:
        self._state.failed_count += 1
        if self._state.failed_count >= self.max_attempts:
            self._state.locked_until = utc_now() + timedelta(seconds=self.lock_seconds)

    def register_success(self) -> None:
        self._state = AttemptState()

