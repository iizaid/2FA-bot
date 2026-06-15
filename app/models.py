from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.utils.time import utc_now


class Base(DeclarativeBase):
    pass


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (
        UniqueConstraint("service_name", "account_label", "issuer", name="uq_account_identity"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    service_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    account_label: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    issuer: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    encrypted_secret: Mapped[str] = mapped_column(Text, nullable=False)
    algorithm: Mapped[str] = mapped_column(String(20), default="SHA1", nullable=False)
    digits: Mapped[int] = mapped_column(Integer, default=6, nullable=False)
    period: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class VaultState(Base):
    __tablename__ = "vault_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    pin_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    lock_timeout_seconds: Mapped[int] = mapped_column(Integer, default=180, nullable=False)
    code_message_ttl_seconds: Mapped[int] = mapped_column(Integer, default=45, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
