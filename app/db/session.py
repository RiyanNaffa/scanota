"""app/db/session.py – SQLAlchemy engines and session dependency."""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings


def _make_engine(url: str, readonly: bool = False):
    connect_args: dict = {}
    kwargs: dict = {
        "pool_pre_ping": True,
        "pool_size": 5,
        "max_overflow": 10,
    }
    return create_engine(url, connect_args=connect_args, **kwargs)


_settings = get_settings()

engine = _make_engine(_settings.database_url)
ro_engine = _make_engine(_settings.database_readonly_url, readonly=True)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
ROSessionLocal = sessionmaker(bind=ro_engine, autocommit=False, autoflush=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: yields a read-write session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_ro_db() -> Generator[Session, None, None]:
    """FastAPI dependency: yields a read-only session."""
    db = ROSessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db() -> bool:
    """Return True if the database is reachable."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
