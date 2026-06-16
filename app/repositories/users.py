from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from telegram import User as TelegramUser

from app.models import User
from app.utils.time import utc_now


class UserRepository:
    def __init__(self, session: Session, *, admin_telegram_ids: set[int] | None = None) -> None:
        self.session = session
        self.admin_telegram_ids = admin_telegram_ids or set()

    def get_by_telegram_id(self, telegram_id: int) -> User | None:
        stmt = select(User).where(User.telegram_id == telegram_id)
        return self.session.execute(stmt).scalar_one_or_none()

    def get(self, user_id: str) -> User | None:
        return self.session.get(User, user_id)

    def get_or_create_from_telegram(self, telegram_user: TelegramUser) -> User:
        user = self.get_by_telegram_id(telegram_user.id)
        now = utc_now()
        role = "admin" if telegram_user.id in self.admin_telegram_ids else "user"
        if user is None:
            user = User(
                telegram_id=telegram_user.id,
                username=telegram_user.username,
                first_name=telegram_user.first_name,
                last_name=telegram_user.last_name,
                language_code=telegram_user.language_code,
                role=role,
                last_seen_at=now,
            )
            self.session.add(user)
        else:
            user.username = telegram_user.username
            user.first_name = telegram_user.first_name
            user.last_name = telegram_user.last_name
            user.language_code = telegram_user.language_code
            user.role = "admin" if telegram_user.id in self.admin_telegram_ids else user.role
            user.last_seen_at = now
            user.updated_at = now
        self.session.flush()
        return user

    def accept_terms(self, user: User) -> None:
        user.accepted_terms_at = utc_now()
        user.updated_at = utc_now()
        self.session.flush()

    def set_status(self, user_id: str, status: str) -> bool:
        user = self.get(user_id)
        if user is None:
            return False
        user.status = status
        user.updated_at = utc_now()
        self.session.flush()
        return True

    def set_status_by_telegram_id(self, telegram_id: int, status: str) -> User | None:
        user = self.get_by_telegram_id(telegram_id)
        if user is None:
            return None
        user.status = status
        user.updated_at = utc_now()
        self.session.flush()
        return user

    def count_by_status(self, status: str | None = None) -> int:
        stmt = select(func.count(User.id))
        if status:
            stmt = stmt.where(User.status == status)
        return int(self.session.scalar(stmt) or 0)

    def list_recent(self, limit: int = 20) -> Sequence[User]:
        stmt = select(User).order_by(User.last_seen_at.desc().nullslast()).limit(limit)
        return self.session.execute(stmt).scalars().all()

    def list_active_telegram_ids(self) -> Sequence[int]:
        stmt = select(User.telegram_id).where(User.status == "active")
        return self.session.execute(stmt).scalars().all()
