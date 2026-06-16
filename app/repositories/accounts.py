from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import VaultAccount
from app.utils.time import utc_now


class AccountRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_for_user(
        self,
        *,
        user_id: str,
        vault_id: str,
        service_name: str,
        account_label: str,
        issuer: str | None,
        encrypted_secret: bytes,
        encrypted_metadata: dict | None = None,
        algorithm: str = "SHA1",
        digits: int = 6,
        period: int = 30,
    ) -> VaultAccount:
        account = VaultAccount(
            user_id=user_id,
            vault_id=vault_id,
            service_name=service_name.strip(),
            account_label=account_label.strip(),
            issuer=issuer.strip() if issuer else None,
            encrypted_secret=encrypted_secret,
            encrypted_metadata=encrypted_metadata,
            algorithm=algorithm.upper(),
            digits=digits,
            period=period,
        )
        self.session.add(account)
        self.session.flush()
        return account

    def list_for_user(self, user_id: str) -> Sequence[VaultAccount]:
        stmt = (
            select(VaultAccount)
            .where(VaultAccount.user_id == user_id)
            .order_by(VaultAccount.service_name.asc(), VaultAccount.account_label.asc())
        )
        return self.session.execute(stmt).scalars().all()

    def get_for_user(self, user_id: str, account_id: str) -> VaultAccount | None:
        stmt = select(VaultAccount).where(VaultAccount.user_id == user_id, VaultAccount.id == account_id)
        return self.session.execute(stmt).scalar_one_or_none()

    def search_for_user(self, user_id: str, query: str) -> Sequence[VaultAccount]:
        pattern = f"%{query.strip()}%"
        stmt = (
            select(VaultAccount)
            .where(
                VaultAccount.user_id == user_id,
                or_(VaultAccount.service_name.ilike(pattern), VaultAccount.account_label.ilike(pattern)),
            )
            .order_by(VaultAccount.service_name.asc(), VaultAccount.account_label.asc())
        )
        return self.session.execute(stmt).scalars().all()

    def count_for_user(self, user_id: str) -> int:
        stmt = select(func.count(VaultAccount.id)).where(VaultAccount.user_id == user_id)
        return int(self.session.scalar(stmt) or 0)

    def count_all(self) -> int:
        return int(self.session.scalar(select(func.count(VaultAccount.id))) or 0)

    def rename_for_user(self, user_id: str, account_id: str, service_name: str, account_label: str) -> VaultAccount | None:
        account = self.get_for_user(user_id, account_id)
        if account is None:
            return None
        account.service_name = service_name.strip()
        account.account_label = account_label.strip()
        account.updated_at = utc_now()
        self.session.flush()
        return account

    def mark_used_for_user(self, user_id: str, account_id: str) -> None:
        account = self.get_for_user(user_id, account_id)
        if account is not None:
            account.last_used_at = utc_now()
            self.session.flush()

    def delete_for_user(self, user_id: str, account_id: str) -> bool:
        account = self.get_for_user(user_id, account_id)
        if account is None:
            return False
        self.session.delete(account)
        self.session.flush()
        return True

    def find_duplicate_for_user(
        self, user_id: str, service_name: str, account_label: str, issuer: str | None
    ) -> VaultAccount | None:
        stmt = select(VaultAccount).where(
            VaultAccount.user_id == user_id,
            VaultAccount.service_name == service_name.strip(),
            VaultAccount.account_label == account_label.strip(),
            VaultAccount.issuer == (issuer.strip() if issuer else None),
        )
        return self.session.execute(stmt).scalar_one_or_none()
