# app/adapters/persistence/lexicon/__init__.py
"""
lexicon/__init__.py
-------------------

Public entrypoint for the lexicon subsystem.

This module re-exports the most common APIs so other parts of the system can do:

    from lexicon import get_index, lookup_lemma, lookup_form

without importing submodules individually.

Design goals
============
- Stable public surface: keep call sites simple.
- Enterprise-grade robustness: avoid import-time side effects, keep types stable,
  and provide backwards-compatible aliasing where practical.
- Explicit separation of concerns:
    - loader.py: filesystem + JSON merging + normalization into a flat mapping
    - cache.py: in-memory caching of per-language indices
    - normalization.py: key normalization helpers
    - schema.py: validation helpers
    - types.py: lexicon data models (BaseLexicalEntry, Lexeme, etc.)
"""

from __future__ import annotations

from typing import Any, Optional

from .cache import clear_cache, cached_languages, get_or_build_index, preload_languages
from .loader import available_languages, load_lexicon
from .normalization import (
    build_normalized_index,
    normalize_for_lookup,
    normalize_whitespace,
    standardize_punctuation,
    strip_diacritics,
)
from .schema import (
    SCHEMA_VERSION,
    SchemaIssue,
    get_schema_version_from_data,
    raise_if_invalid,
    validate_lexicon_structure,
)
from .types import (
    BaseLexicalEntry,
    Lexeme,
    Lexicon,
    LexiconMeta,
    NameTemplate,
    NationalityEntry,
    ProfessionEntry,
    TitleEntry,
    HonourEntry,
)


# ---------------------------------------------------------------------------
# Index access
# ---------------------------------------------------------------------------


def get_index(lang: str):
    """
    Return the cached per-language index, building it on first use.

    This delegates to `lexicon.cache.get_or_build_index`.
    """
    return get_or_build_index(lang)


# ---------------------------------------------------------------------------
# Convenience wrappers (enterprise-safe, best-effort)
# ---------------------------------------------------------------------------


def lookup_lemma(
    lang: str,
    lemma: str,
    pos: Optional[str] = None,
) -> Optional[Any]:
    """
    Look up an entry by lemma (and optionally POS).

    Notes:
    - The exact return type depends on the concrete LexiconIndex implementation.
      In this codebase, LexiconIndex currently indexes ProfessionEntry /
      NationalityEntry / BaseLexicalEntry.
    - If POS is not supported by the index implementation, it will be ignored.
    """
    idx = get_index(lang)

    # Prefer a rich method if present (future-proofing)
    if hasattr(idx, "lookup_by_lemma"):
        try:
            return idx.lookup_by_lemma(lemma, pos=pos)  # type: ignore[attr-defined]
        except TypeError:
            return idx.lookup_by_lemma(lemma)  # type: ignore[attr-defined]

    # Fallback to available lookups (current LexiconIndex API)
    entry = None
    if hasattr(idx, "lookup_profession"):
        entry = idx.lookup_profession(lemma)  # type: ignore[attr-defined]
        if entry is not None:
            return entry

    if hasattr(idx, "lookup_nationality"):
        entry = idx.lookup_nationality(lemma)  # type: ignore[attr-defined]
        if entry is not None:
            return entry

    if hasattr(idx, "lookup_any"):
        return idx.lookup_any(lemma)  # type: ignore[attr-defined]

    return None


def lookup_qid(
    lang: str,
    qid: str,
) -> Optional[Any]:
    """
    Look up an entry by a Wikidata QID (best-effort).

    Notes:
    - The current LexiconIndex implementation in `index.py` does not implement
      QID lookups. This wrapper returns None unless the index provides a
      compatible lookup method.
    """
    idx = get_index(lang)

    if hasattr(idx, "lookup_by_qid"):
        return idx.lookup_by_qid(qid)  # type: ignore[attr-defined]

    if hasattr(idx, "lookup_qid"):
        return idx.lookup_qid(qid)  # type: ignore[attr-defined]

    return None


def lookup_form(
    lang: str,
    lemma: str,
    features: Optional[dict[str, Any]] = None,
    pos: Optional[str] = None,
) -> Optional[Any]:
    """
    Look up a surface form for a lemma given morphological features (best-effort).

    Notes:
    - The current LexiconIndex in `index.py` does not expose a morphology API.
      This wrapper supports future indices that implement `lookup_form(...)`.
    """
    idx = get_index(lang)
    feats = features or {}

    if hasattr(idx, "lookup_form"):
        try:
            return idx.lookup_form(lemma=lemma, features=feats, pos=pos)  # type: ignore[attr-defined]
        except TypeError:
            # tolerate older signatures
            return idx.lookup_form(lemma, feats)  # type: ignore[attr-defined]

    return None


__all__ = [
    # Core access
    "get_index",
    # Convenience lookups
    "lookup_lemma",
    "lookup_qid",
    "lookup_form",
    # Loader
    "load_lexicon",
    "available_languages",
    # Cache controls
    "get_or_build_index",
    "preload_languages",
    "clear_cache",
    "cached_languages",
    # Normalization
    "normalize_for_lookup",
    "normalize_whitespace",
    "standardize_punctuation",
    "strip_diacritics",
    "build_normalized_index",
    # Schema / validation
    "SCHEMA_VERSION",
    "SchemaIssue",
    "get_schema_version_from_data",
    "validate_lexicon_structure",
    "raise_if_invalid",
    # Types
    "LexiconMeta",
    "Lexicon",
    "BaseLexicalEntry",
    "Lexeme",
    "ProfessionEntry",
    "NationalityEntry",
    "TitleEntry",
    "HonourEntry",
    "NameTemplate",
]
