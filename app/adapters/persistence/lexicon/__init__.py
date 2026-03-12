# app/adapters/persistence/lexicon/__init__.py
"""
Public entrypoint for the lexicon subsystem.

This package now exposes two layers of API:

1. Legacy / storage-oriented APIs
   - load_lexicon(...)
   - get_index(...)
   - lookup_lemma(...)
   - lookup_qid(...)
   - lookup_form(...)

2. Batch 5 lexical-resolution APIs
   - lexical_resolution module namespace
   - entity_resolution module namespace
   - predicate_resolution module namespace

The legacy lookup surface remains stable for existing callers, while the new
planner-first runtime can import the lexical-resolution layer from the same
package boundary.

Notes
-----
- Keep this file import-light and side-effect free.
- Prefer re-exporting stable public names here rather than forcing callers
  to know submodule layout.
- New lexical-resolution submodules are exported as namespaces to avoid
  overcommitting to exact helper names while the Batch 5 API settles.
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
    HonourEntry,
    Lexeme,
    Lexicon,
    LexiconMeta,
    NameTemplate,
    NationalityEntry,
    ProfessionEntry,
    TitleEntry,
)

# Batch 5 bridge / runtime exports
from .aw_lexeme_bridge import lexeme_from_z_object, lexemes_from_z_list
from . import lexical_resolution
from . import entity_resolution
from . import predicate_resolution


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
# Convenience wrappers (legacy-safe, best-effort)
# ---------------------------------------------------------------------------


def lookup_lemma(
    lang: str,
    lemma: str,
    pos: Optional[str] = None,
) -> Optional[Any]:
    """
    Look up an entry by lemma (and optionally POS), best-effort.

    Notes:
    - The exact return type depends on the concrete LexiconIndex implementation.
    - If POS is not supported by the index implementation, it will be ignored.
    """
    idx = get_index(lang)

    if hasattr(idx, "lookup_by_lemma"):
        try:
            return idx.lookup_by_lemma(lemma, pos=pos)  # type: ignore[attr-defined]
        except TypeError:
            return idx.lookup_by_lemma(lemma)  # type: ignore[attr-defined]

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


def lookup_qid(lang: str, qid: str) -> Optional[Any]:
    """
    Look up an entry by a Wikidata QID (best-effort).

    Notes:
    - If the index doesn't support QID lookups, returns None.
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
    - The current LexiconIndex does not expose a full morphology API.
      This wrapper supports future indices that implement `lookup_form(...)`.
    """
    idx = get_index(lang)
    feats: dict[str, Any] = features or {}

    if hasattr(idx, "lookup_form"):
        try:
            return idx.lookup_form(lemma=lemma, features=feats, pos=pos)  # type: ignore[attr-defined]
        except TypeError:
            return idx.lookup_form(lemma, feats)  # type: ignore[attr-defined]

    return None


# ---------------------------------------------------------------------------
# Backwards-compatible aliases
# ---------------------------------------------------------------------------

warmup_languages = preload_languages


__all__ = [
    # Core access
    "get_index",
    "get_or_build_index",
    # Convenience lookups
    "lookup_lemma",
    "lookup_qid",
    "lookup_form",
    # Loader
    "load_lexicon",
    "available_languages",
    # Cache controls
    "preload_languages",
    "warmup_languages",
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
    # AW / ingestion bridge
    "lexeme_from_z_object",
    "lexemes_from_z_list",
    # Batch 5 runtime namespaces
    "lexical_resolution",
    "entity_resolution",
    "predicate_resolution",
]