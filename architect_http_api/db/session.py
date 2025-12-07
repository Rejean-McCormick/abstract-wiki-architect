# architect_http_api/db/session.py

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from architect_http_api.config import get_config

# ---------------------------------------------------------------------------
# Engine / Session factory
# ---------------------------------------------------------------------------

# Use the config factory to get the current configuration
config = get_config()

# Fallback database URL if not set in config (though config should handle defaults)
# This assumes your config object doesn't have a direct DATABASE_URL field yet,
# but typically one would add it or construct it here.
# For this fix, let's assume a default SQLite path if not present, or construct it.
# Since your config.py manages HOST/PORT but not explicitly DB URL in the snippet provided,
# we will use a local SQLite default here for safety, or read an env var directly if preferred.
# However, the best practice is to read it from the config object if available.
# Let's assume for this fix we use a standard default or read from env.
import os
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./abstract_wiki_architect.db")


# SQLite needs a special flag when used in a multi-threaded web app.
connect_args: dict[str, object] = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    DATABASE_URL,
    echo=config.debug, # Use debug flag from config
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

# Base for all ORM models;
# import this in architect_http_api/db/models.py
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

# Alias get_db as get_session for compatibility if needed by other modules
get_session = get_db

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


__all__ = ["engine", "SessionLocal", "Base", "get_db", "get_session", "db_session"]