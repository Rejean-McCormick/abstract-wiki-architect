# app\adapters\persistence\lexicon\init.py
# lexicon\init.py
"""
lexicon/__init__.py
-------------------

Public entrypoint for the lexicon subsystem.

This package provides:

- Data types:
    - Lexeme, Sense, Form, etc. (see lexicon.types)
- Loading:
    - load_lexicon(lang) to read JSON lexicon files from data/lexicon/.
- Indexing & lookup:
    - get_index(lang) to obtain a LexiconIndex (cached).
    - lookup_lemma(lang, lemma, pos=None) to resolve lemmas to lexemes.
    - lookup_qid(lang, qid) to resolve Wikidata IDs to lexemes.
    - lookup_form(lang, lemma, features) to get an inflected form.
- Normalization:
    - normalize_lemma_key(...) for robust lemma key normalization.

Typical usage
=============

    from lexicon import (
        get_index,
        lookup_lemma,
        lookup_qid,
        Lexeme,
    )

    # Get a per-language index
    idx = get_index("en")

    # Look up by lemma
    lex = lookup_lemma("en", "physicist", pos="NOUN")

    # Or via index methods directly
    lex2 = idx.lookup_by_lemma("physicist", pos="NOUN")

This module intentionally re-exports the most common APIs so other
parts of the system can do:

    from lexicon import lookup_lemma

instead of importing submodules individually.
"""

from __future__ import annotations

from typing import Optional, Any

from .types import Lexeme, Sense, Form  # type: ignore[import-not-found]
from .loader import load_lexicon  # type: ignore[import-not-found]
from .index import (  # type: ignore[import-not-found]
    LexiconIndex,
    get_index,
)
from .normalization import normalize_lemma_key  # type: ignore[import-not-found]


# ---------------------------------------------------------------------------
# Convenience wrapper functions
# ---------------------------------------------------------------------------


def lookup_lemma(
    lang: str,
    lemma: str,
    pos: Optional[str] = None,
) -> Optional[Lexeme]:
    """
    Convenience wrapper to look up a lexeme by lemma (and optionally POS).

    Args:
        lang:
            Language code (e.g. "en", "fr", "sw").
        lemma:
            Lemma string as used in test data / semantics.
        pos:
            Optional coarse part of speech ("NOUN", "ADJ", "VERB", ...).

    Returns:
        A Lexeme instance if found, otherwise None.
    """
    index = get_index(lang)
    return index.lookup_by_lemma(lemma, pos=pos)


def lookup_qid(
    lang: str,
    qid: str,
) -> Optional[Lexeme]:
    """
    Convenience wrapper to look up a lexeme by Wikidata QID or lexeme ID.

    Args:
        lang:
            Language code.
        qid:
            Identifier such as "Q123" or "L456-lemma". The exact format
            is up to the index implementation.

    Returns:
        A Lexeme instance if found, otherwise None.
    """
    index = get_index(lang)
    return index.lookup_by_qid(qid)


def lookup_form(
    lang: str,
    lemma: str,
    features: Optional[dict[str, Any]] = None,
    pos: Optional[str] = None,
) -> Optional[Form]:
    """
    Convenience wrapper to look up a surface form for a lemma given
    some morphological features.

    Args:
        lang:
            Language code.
        lemma:
            Base lemma.
        features:
            Feature bundle, e.g. {"number": "pl", "gender": "fem"}.
        pos:
            Optional part of speech hint.

    Returns:
        A Form instance if a matching form is found, otherwise None.
    """
    if features is None:
        features = {}

    index = get_index(lang)
    return index.lookup_form(lemma=lemma, features=features, pos=pos)


__all__ = [
    # Types
    "Lexeme",
    "Sense",
    "Form",
    "LexiconIndex",
    # Loading / index
    "load_lexicon",
    "get_index",
    # Lookups
    "lookup_lemma",
    "lookup_qid",
    "lookup_form",
    # Normalization
    "normalize_lemma_key",
]
