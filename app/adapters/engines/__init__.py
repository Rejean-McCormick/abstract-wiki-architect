# app\adapters\engines\__init__.py
"""
Grammar Engine Adapters.

This package contains the concrete implementations of the `IGrammarEngine` port.
It provides the mechanisms to transform abstract Semantic Frames into text using
different strategies:

1. GFGrammarEngine: The production-grade engine using the compiled PGF binary (High Fidelity).
2. PidginGrammarEngine: The fallback/prototyping engine using pure Python string manipulation (Low Fidelity).
"""

from .gf_runtime import GFGrammarEngine
from .pidgin_runtime import PidginGrammarEngine

__all__ = [
    "GFGrammarEngine",
    "PidginGrammarEngine",
]