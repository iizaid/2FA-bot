from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import SecurityEvent


class SecurityEventRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def record(
        self,
        *,
        event_type: str,
        severity: str = "info",
        user_id: str | None = None,
        telegram_id: int | None = None,
        safe_metadata: dict | None = None,
    ) -> SecurityEvent:
        event = SecurityEvent(
            user_id=user_id,
            telegram_id=telegram_id,
            event_type=event_type,
            severity=severity,
            safe_metadata=safe_metadata,
        )
        self.session.add(event)
        self.session.flush()
        return event

    def recent(self, limit: int = 20) -> Sequence[SecurityEvent]:
        stmt = select(SecurityEvent).order_by(SecurityEvent.created_at.desc()).limit(limit)
        return self.session.execute(stmt).scalars().all()
