from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import EncryptedExport


class ExportRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def record(self, *, user_id: str, file_name: str, export_hash: str | None) -> EncryptedExport:
        export = EncryptedExport(user_id=user_id, file_name=file_name, export_hash=export_hash)
        self.session.add(export)
        self.session.flush()
        return export
