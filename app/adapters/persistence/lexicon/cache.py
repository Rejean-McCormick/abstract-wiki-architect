# lexicon\cache.py
"""
lexicon/cache.py
----------------

In-memory caching utilities for the lexicon subsystem.

Goals
=====

- Avoid re-parsing large JSON lexicon files on every lookup.
- Provide a simple API to:
    - get or build a per-language LexiconIndex,
    - preload indexes for multiple languages,
    - clear or inspect the cache.

This module is intentionally lightweight and does not persist anything to
disk. If you later add a disk-based cache, this is a good place to hook
it in (or to delegate to a more advanced caching layer).

Typical usage
=============

    from lexicon.cache import get_or_build_index, preload_languages

    # Preload for a demo
    preload_languages(["en", "fr", "sw"])

    # Later, when rendering:
    idx = get_or_build_index("en")
    lex = idx.lookup_by_lemma("physicist", pos="NOUN")

Implementation note
===================

This module is usually used *by* lexicon.index (to back `get_index`),
not the other way around. The separation is purely organizational.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from .loader import load_lexicon  # type: ignore[import-not-found]
from .index import LexiconIndex  # type: ignore[import-not-found]


# ---------------------------------------------------------------------------
# Internal state
# ---------------------------------------------------------------------------

# Map: language code → LexiconIndex
_INDEX_CACHE: Dict[str, LexiconIndex] = {}


# ---------------------------------------------------------------------------
# Core cache API
# ---------------------------------------------------------------------------


def get_or_build_index(lang: str) -> LexiconIndex:
    """
    Get a LexiconIndex for the given language, building and caching it
    if necessary.

    Args:
        lang:
            Language code (e.g. "en", "fr", "sw").

    Returns:
        A LexiconIndex instance for that language.

    Raises:
        Any exceptions raised by `load_lexicon` or `LexiconIndex` factory
        methods (e.g. file not found, malformed JSON).
    """
    lang = lang.strip()
    if not lang:
        raise ValueError("Language code must be a non-empty string.")

    if lang in _INDEX_CACHE:
        return _INDEX_CACHE[lang]

    # Load raw lexicon data and build an index
    lexemes = load_lexicon(lang)
    index = LexiconIndex.from_lexemes(lexemes)
    _INDEX_CACHE[lang] = index
    return index


def set_index(lang: str, index: LexiconIndex) -> None:
    """
    Manually insert or override a cached index for a language.

    This is mainly useful for testing, or if you build the index by
    other means and want to inject it into the cache.
    """
    lang = lang.strip()
    if not lang:
        raise ValueError("Language code must be a non-empty string.")
    _INDEX_CACHE[lang] = index


def clear_cache(lang: Optional[str] = None) -> None:
    """
    Clear the in-memory cache.

    Args:
        lang:
            If provided, only clear the cache entry for this language.
            If None, clear the entire cache.
    """
    global _INDEX_CACHE

    if lang is None:
        _INDEX_CACHE = {}
    else:
        _INDEX_CACHE.pop(lang.strip(), None)


def cached_languages() -> List[str]:
    """
    Return the list of language codes currently present in the cache.
    """
    return sorted(_INDEX_CACHE.keys())


def preload_languages(langs: Iterable[str]) -> None:
    """
    Preload lexicon indexes for a list of languages.

    This is mainly useful for demos or benchmarking where you want to
    avoid measuring the initial load time in the middle of a run.

    Args:
        langs:
            Iterable of language codes to preload.
    """
    for lang in langs:
        lang = str(lang).strip()
        if not lang:
            continue
        # Build and cache; ignore errors only if you want to be strict.
        get_or_build_index(lang)


__all__ = [
    "get_or_build_index",
    "set_index",
    "clear_cache",
    "cached_languages",
    "preload_languages",
]
