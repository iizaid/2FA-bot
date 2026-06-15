from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import VaultState
from app.utils.time import utc_now


class SettingsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_or_create(self, *, lock_timeout_seconds: int, code_message_ttl_seconds: int) -> VaultState:
        state = self.session.get(VaultState, 1)
        if state is None:
            state = VaultState(
                id=1,
                lock_timeout_seconds=lock_timeout_seconds,
                code_message_ttl_seconds=code_message_ttl_seconds,
            )
            self.session.add(state)
            self.session.flush()
        return state

    def set_pin_hash(self, state: VaultState, pin_hash: str) -> None:
        state.pin_hash = pin_hash
        state.updated_at = utc_now()
        self.session.flush()

    def update_lock_timeout(self, state: VaultState, seconds: int) -> None:
        state.lock_timeout_seconds = seconds
        state.updated_at = utc_now()
        self.session.flush()

    def update_code_ttl(self, state: VaultState, seconds: int) -> None:
        state.code_message_ttl_seconds = seconds
        state.updated_at = utc_now()
        self.session.flush()
