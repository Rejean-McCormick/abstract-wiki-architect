"""
architect_http_api.db
=====================

Database package for the Abstract Wiki Architect HTTP API.

This module centralizes the public DB primitives so the rest of the
service can import them from a single place, e.g.:

    from architect_http_api.db import Base, engine, SessionLocal, get_db
"""

from .session import engine, SessionLocal, get_db
from .models import Base

__all__ = [
    "Base",
    "engine",
    "SessionLocal",
    "get_db",
]
