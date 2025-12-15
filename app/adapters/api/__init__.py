# app\adapters\api\__init__.py
"""
REST API Adapter.

This package acts as the HTTP entry point for the Abstract Wiki.
It is built on FastAPI and follows the Hexagonal Architecture principles:
- It depends on `app.core` (Use Cases & Models).
- It wires the `app.shared.container` to inject dependencies.
- It does NOT contain business logic.
"""

from .main import create_app

__all__ = ["create_app"]