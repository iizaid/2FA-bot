from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Vault
from app.utils.time import utc_now


class VaultRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_for_user(self, user_id: str) -> Vault | None:
        stmt = select(Vault).where(Vault.user_id == user_id)
        return self.session.execute(stmt).scalar_one_or_none()

    def create_for_user(self, *, user_id: str, kdf_salt: bytes, passphrase_hash: str, encryption_scheme: str) -> Vault:
        vault = Vault(
            user_id=user_id,
            kdf_salt=kdf_salt,
            passphrase_hash=passphrase_hash,
            encryption_scheme=encryption_scheme,
        )
        self.session.add(vault)
        self.session.flush()
        return vault

    def mark_unlocked(self, vault: Vault) -> None:
        vault.last_unlocked_at = utc_now()
        vault.locked_at = None
        vault.updated_at = utc_now()
        self.session.flush()

    def mark_locked(self, vault: Vault) -> None:
        vault.locked_at = utc_now()
        vault.updated_at = utc_now()
        self.session.flush()
