# app/adapters/persistence/lexicon/cache.py
# lexicon/cache.py
"""
lexicon/cache.py
----------------

Enterprise-grade in-memory caching utilities for the lexicon subsystem.

Goals
=====
- Avoid re-parsing large lexicon data on every lookup.
- Provide a small, testable API to:
    - get/build a per-language LexiconIndex,
    - preload indexes for multiple languages,
    - clear or inspect the cache.
- Thread-safe for typical multi-threaded app servers.
- Deterministic behavior and explicit error surfaces.

This module does not persist anything to disk.

Implementation notes
====================
- We cache by normalized language code (casefold + strip).
- We use a lock to protect cache mutations.
- We provide a `warmup_languages` alias for clarity in app startup code.
"""

from __future__ import annotations

import threading
from typing import Dict, Iterable, List, Optional

from .loader import load_lexicon  # type: ignore[import-not-found]
from .index import LexiconIndex  # type: ignore[import-not-found]
from .types import Lexicon  # type: ignore[import-not-found]

# ---------------------------------------------------------------------------
# Internal state
# ---------------------------------------------------------------------------

# Map: normalized language code → LexiconIndex
_INDEX_CACHE: Dict[str, LexiconIndex] = {}

# Lock for cache mutations / double-checked creation
_CACHE_LOCK = threading.RLock()


def _norm_lang(lang: str) -> str:
    if not isinstance(lang, str):
        return ""
    return lang.strip().casefold()


# ---------------------------------------------------------------------------
# Core cache API
# ---------------------------------------------------------------------------


def get_or_build_index(lang: str) -> LexiconIndex:
    """
    Get a LexiconIndex for the given language, building and caching it if needed.

    Args:
        lang: Language code (e.g. "en", "fr", "sw").

    Returns:
        LexiconIndex for that language.

    Raises:
        ValueError: empty/invalid lang code.
        FileNotFoundError / JSON errors: bubbled from loader.
        Any exceptions from LexiconIndex construction.
    """
    nlang = _norm_lang(lang)
    if not nlang:
        raise ValueError("Language code must be a non-empty string.")

    # Fast path (no lock) for already-cached entries.
    existing = _INDEX_CACHE.get(nlang)
    if existing is not None:
        return existing

    # Slow path: build under lock, double-checking.
    with _CACHE_LOCK:
        existing = _INDEX_CACHE.get(nlang)
        if existing is not None:
            return existing

        lex = load_lexicon(nlang)

        # load_lexicon historically returned Dict[str, Dict[str, Any]] in this codebase,
        # but the new enterprise-grade path expects Lexicon for LexiconIndex construction.
        # Accept both for compatibility.
        if isinstance(lex, Lexicon):
            index = LexiconIndex(lex)
        else:
            # If a legacy index factory exists in older branches, keep it as fallback.
            # Otherwise, require callers to migrate loader -> Lexicon.
            if hasattr(LexiconIndex, "from_lexemes"):
                index = LexiconIndex.from_lexemes(lex)  # type: ignore[attr-defined]
            else:
                raise TypeError(
                    "load_lexicon() returned legacy mapping, but LexiconIndex requires "
                    "a Lexicon. Migrate loader to return Lexicon or add LexiconIndex.from_lexemes()."
                )

        _INDEX_CACHE[nlang] = index
        return index


def set_index(lang: str, index: LexiconIndex) -> None:
    """
    Manually insert or override a cached index for a language.
    Useful for tests or dependency injection.
    """
    nlang = _norm_lang(lang)
    if not nlang:
        raise ValueError("Language code must be a non-empty string.")
    if index is None:
        raise ValueError("Index must be non-null.")

    with _CACHE_LOCK:
        _INDEX_CACHE[nlang] = index


def clear_cache(lang: Optional[str] = None) -> None:
    """
    Clear the in-memory cache.

    Args:
        lang: if provided, clears only that language; otherwise clears all.
    """
    with _CACHE_LOCK:
        if lang is None:
            _INDEX_CACHE.clear()
            return
        _INDEX_CACHE.pop(_norm_lang(lang), None)


def cached_languages() -> List[str]:
    """
    Return cached language codes (normalized).
    """
    with _CACHE_LOCK:
        return sorted(_INDEX_CACHE.keys())


def preload_languages(langs: Iterable[str]) -> None:
    """
    Preload lexicon indexes for a list of languages.

    This is useful for startup warmups. Errors are propagated; the caller
    should decide whether to catch and continue.
    """
    for lang in langs:
        nlang = _norm_lang(str(lang))
        if not nlang:
            continue
        get_or_build_index(nlang)


# Alias commonly used name in production startup code.
warmup_languages = preload_languages


__all__ = [
    "get_or_build_index",
    "set_index",
    "clear_cache",
    "cached_languages",
    "preload_languages",
    "warmup_languages",
]
