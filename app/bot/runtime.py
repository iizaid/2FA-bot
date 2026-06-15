from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.services.auth import VaultAuthService
from app.services.backup import BackupService
from app.services.encryption import EncryptionService
from app.services.rate_limit import UnlockRateLimiter


@dataclass
class BotRuntime:
    settings: Settings
    session_factory: sessionmaker[Session]
    encryption: EncryptionService
    auth: VaultAuthService
    rate_limiter: UnlockRateLimiter
    backup: BackupService

