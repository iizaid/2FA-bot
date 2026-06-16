from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import VaultSession
from app.utils.time import utc_now


class VaultSessionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def replace_for_user(self, user_id: str, unlocked_until: datetime) -> VaultSession:
        self.delete_for_user(user_id)
        vault_session = VaultSession(user_id=user_id, unlocked_until=unlocked_until)
        self.session.add(vault_session)
        self.session.flush()
        return vault_session

    def get_active_for_user(self, user_id: str) -> VaultSession | None:
        stmt = select(VaultSession).where(
            VaultSession.user_id == user_id,
            VaultSession.unlocked_until > utc_now(),
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def delete_for_user(self, user_id: str) -> None:
        self.session.execute(delete(VaultSession).where(VaultSession.user_id == user_id))
        self.session.flush()
