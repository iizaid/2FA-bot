from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.models import Base


class DatabaseConfigurationError(RuntimeError):
    pass


def build_engine(settings: Settings):
    connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
    return create_engine(settings.database_url, future=True, connect_args=connect_args)


def build_session_factory(settings: Settings) -> sessionmaker[Session]:
    engine = build_engine(settings)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def init_db(settings: Settings) -> None:
    if settings.app_env.lower() == "production" and settings.auto_create_tables:
        raise DatabaseConfigurationError("AUTO_CREATE_TABLES=true is not allowed when APP_ENV=production")
    if not settings.auto_create_tables:
        return
    if settings.app_env.lower() not in {"development", "test"}:
        raise DatabaseConfigurationError("AUTO_CREATE_TABLES is only allowed in development or test")
    engine = build_engine(settings)
    Base.metadata.create_all(engine)


@contextmanager
def session_scope(session_factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
