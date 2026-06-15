from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Account
from app.utils.time import utc_now


class AccountRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        *,
        service_name: str,
        account_label: str,
        issuer: str | None,
        encrypted_secret: str,
        algorithm: str = "SHA1",
        digits: int = 6,
        period: int = 30,
    ) -> Account:
        account = Account(
            service_name=service_name.strip(),
            account_label=account_label.strip(),
            issuer=issuer.strip() if issuer else None,
            encrypted_secret=encrypted_secret,
            algorithm=algorithm.upper(),
            digits=digits,
            period=period,
        )
        self.session.add(account)
        self.session.flush()
        return account

    def list_all(self) -> Sequence[Account]:
        stmt = select(Account).order_by(Account.service_name.asc(), Account.account_label.asc())
        return self.session.execute(stmt).scalars().all()

    def get(self, account_id: int) -> Account | None:
        return self.session.get(Account, account_id)

    def count(self) -> int:
        return int(self.session.scalar(select(func.count(Account.id))) or 0)

    def search(self, query: str) -> Sequence[Account]:
        pattern = f"%{query.strip()}%"
        stmt = (
            select(Account)
            .where(or_(Account.service_name.ilike(pattern), Account.account_label.ilike(pattern)))
            .order_by(Account.service_name.asc(), Account.account_label.asc())
        )
        return self.session.execute(stmt).scalars().all()

    def rename(self, account: Account, service_name: str, account_label: str) -> Account:
        account.service_name = service_name.strip()
        account.account_label = account_label.strip()
        account.updated_at = utc_now()
        self.session.flush()
        return account

    def mark_used(self, account: Account) -> None:
        account.last_used_at = utc_now()
        self.session.flush()

    def delete(self, account: Account) -> None:
        self.session.delete(account)
        self.session.flush()

    def find_duplicate(self, service_name: str, account_label: str, issuer: str | None) -> Account | None:
        stmt = select(Account).where(
            Account.service_name == service_name.strip(),
            Account.account_label == account_label.strip(),
            Account.issuer == (issuer.strip() if issuer else None),
        )
        return self.session.execute(stmt).scalar_one_or_none()

