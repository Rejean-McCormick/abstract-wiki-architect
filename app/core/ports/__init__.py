# app\core\ports\__init__.py
"""
Core Ports (Interfaces).

This package defines the abstract base classes (Protocols) that the
Infrastructure Adapters must implement. These interfaces allow the Core
Domain to interact with the outside world (Database, Redis, GF) without
knowing the implementation details.
"""

from .grammar_engine import IGrammarEngine
from .lexicon_repository import ILexiconRepository
from .message_broker import IMessageBroker

__all__ = [
    "IGrammarEngine",
    "ILexiconRepository",
    "IMessageBroker",
]