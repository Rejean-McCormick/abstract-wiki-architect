# app\adapters\persistence\__init__.py
"""
Persistence Adapters.

This package implements the Repository ports defined in the Core Domain.
It handles the translation between Domain Entities and the underlying storage mechanism
(currently the local file system).

Components:
- FileSystemLexiconRepository: Concrete implementation of ILexiconRepository using JSON/GF files.
"""

from .filesystem_repository import FileSystemLexiconRepository

__all__ = [
    "FileSystemLexiconRepository",
]