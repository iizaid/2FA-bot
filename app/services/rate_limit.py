from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.utils.time import utc_now


@dataclass
class AttemptState:
    failed_count: int = 0
    locked_until: datetime | None = None


@dataclass
class UserRateState:
    message_times: deque[datetime] = field(default_factory=deque)
    add_attempt_times: deque[datetime] = field(default_factory=deque)


class RateLimitService:
    def __init__(
        self,
        *,
        max_unlock_attempts: int = 5,
        lockout_seconds: int = 300,
        global_rate_limit_per_minute: int = 30,
        add_attempts_per_minute: int = 10,
    ) -> None:
        self.max_unlock_attempts = max_unlock_attempts
        self.lockout_seconds = lockout_seconds
        self.global_rate_limit_per_minute = global_rate_limit_per_minute
        self.add_attempts_per_minute = add_attempts_per_minute
        self._unlock_attempts: dict[str, AttemptState] = {}
        self._user_rates: dict[str, UserRateState] = {}
        self._global_times: deque[datetime] = deque()

    def unlock_is_locked(self, user_id: str) -> bool:
        state = self._unlock_attempts.get(user_id, AttemptState())
        if state.locked_until is None:
            return False
        if utc_now() >= state.locked_until:
            self._unlock_attempts[user_id] = AttemptState()
            return False
        return True

    def unlock_seconds_remaining(self, user_id: str) -> int:
        state = self._unlock_attempts.get(user_id, AttemptState())
        if not self.unlock_is_locked(user_id) or state.locked_until is None:
            return 0
        return max(0, int((state.locked_until - utc_now()).total_seconds()))

    def register_unlock_failure(self, user_id: str) -> None:
        state = self._unlock_attempts.setdefault(user_id, AttemptState())
        state.failed_count += 1
        if state.failed_count >= self.max_unlock_attempts:
            state.locked_until = utc_now() + timedelta(seconds=self.lockout_seconds)

    def register_unlock_success(self, user_id: str) -> None:
        self._unlock_attempts[user_id] = AttemptState()

    def allow_message(self, user_id: str) -> bool:
        state = self._user_rates.setdefault(user_id, UserRateState())
        now = utc_now()
        self._prune(state.message_times, now)
        self._prune(self._global_times, now)
        if len(state.message_times) >= self.global_rate_limit_per_minute:
            return False
        if len(self._global_times) >= self.global_rate_limit_per_minute * 100:
            return False
        state.message_times.append(now)
        self._global_times.append(now)
        return True

    def allow_add_attempt(self, user_id: str) -> bool:
        state = self._user_rates.setdefault(user_id, UserRateState())
        now = utc_now()
        self._prune(state.add_attempt_times, now)
        if len(state.add_attempt_times) >= self.add_attempts_per_minute:
            return False
        state.add_attempt_times.append(now)
        return True

    @staticmethod
    def _prune(items: deque[datetime], now: datetime) -> None:
        cutoff = now - timedelta(minutes=1)
        while items and items[0] < cutoff:
            items.popleft()
