from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AdminAuditLog, User, VaultAccount


class AdminRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def stats(self) -> dict[str, int]:
        return {
            "total_users": int(self.session.scalar(select(func.count(User.id))) or 0),
            "active_users": int(self.session.scalar(select(func.count(User.id)).where(User.status == "active")) or 0),
            "blocked_users": int(self.session.scalar(select(func.count(User.id)).where(User.status == "blocked")) or 0),
            "deleted_users": int(self.session.scalar(select(func.count(User.id)).where(User.status == "deleted")) or 0),
            "vault_accounts": int(self.session.scalar(select(func.count(VaultAccount.id))) or 0),
        }

    def record_audit(
        self,
        *,
        admin_user_id: str | None,
        action: str,
        target_user_id: str | None = None,
        safe_metadata: dict | None = None,
    ) -> AdminAuditLog:
        log = AdminAuditLog(
            admin_user_id=admin_user_id,
            action=action,
            target_user_id=target_user_id,
            safe_metadata=safe_metadata,
        )
        self.session.add(log)
        self.session.flush()
        return log
