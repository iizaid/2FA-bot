from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Base, User, Vault
from app.repositories.users import UserRepository
from app.repositories.vaults import VaultRepository
from app.services.auth import VaultAuthService
from app.services.encryption import EncryptionService


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def telegram_user(telegram_id: int, username: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=telegram_id,
        username=username,
        first_name=username.title(),
        last_name=None,
        language_code="en",
    )


def create_user(session: Session, telegram_id: int, username: str) -> User:
    return UserRepository(session).get_or_create_from_telegram(telegram_user(telegram_id, username))


def create_vault(session: Session, user: User, passphrase: str = "correct horse battery staple") -> tuple[Vault, bytes]:
    encryption = EncryptionService()
    auth = VaultAuthService(encryption, 180)
    salt, passphrase_hash, vault_key = auth.create_vault_material(passphrase)
    vault = VaultRepository(session).create_for_user(
        user_id=user.id,
        kdf_salt=salt,
        passphrase_hash=passphrase_hash,
        encryption_scheme=encryption.scheme,
    )
    return vault, vault_key
