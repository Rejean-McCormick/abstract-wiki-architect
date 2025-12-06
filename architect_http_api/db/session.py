from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from architect_http_api.config import settings

# ---------------------------------------------------------------------------
# Engine / Session factory
# ---------------------------------------------------------------------------

DATABASE_URL: str = settings.DATABASE_URL

# SQLite needs a special flag when used in a multi-threaded web app.
connect_args: dict[str, object] = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    DATABASE_URL,
    echo=getattr(settings, "DB_ECHO", False),
    future=True,
    connect_args=connect_args,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    class_=Session,
)

# Base for all ORM models; import this in architect_http_api/db/models.py
Base = declarative_base()


# ---------------------------------------------------------------------------
# FastAPI dependency / helper
# ---------------------------------------------------------------------------

def get_db() -> Generator[Session, None, None]:
    """
    FastAPI-style dependency that yields a database session and ensures it
    is closed afterwards.

    Usage:

        from fastapi import Depends
        from architect_http_api.db.session import get_db

        @router.get("/entities")
        def list_entities(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def db_session() -> Generator[Session, None, None]:
    """
    Context manager for non-FastAPI usage, e.g. scripts or background jobs.

        from architect_http_api.db.session import db_session

        with db_session() as db:
            ...
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


__all__ = ["engine", "SessionLocal", "Base", "get_db", "db_session"]
