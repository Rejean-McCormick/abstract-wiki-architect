# app/adapters/persistence/lexicon/normalization.py
# lexicon/normalization.py
"""
lexicon.normalization
=====================

Utility functions to normalize lemma strings and keys so that different
lexicon files (en/fr/sw/ja/…) can share a common lookup strategy.

Design goals
------------
- Tolerant of user input: capitalization, extra spaces, punctuation variants.
- Stable canonical form usable as a dictionary key.
- Unicode-safe and script-agnostic (Latin, Cyrillic, CJK, Arabic, …).
- Enterprise-grade determinism:
    - explicit, documented normalization pipeline
    - configurable "aggressiveness" helpers for callers
    - safe collision reporting for index-building (optional)

Typical usage
-------------
>>> from lexicon.normalization import normalize_for_lookup
>>> normalize_for_lookup("  Nobel   Prize – in Physics ")
'nobel prize - in physics'
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

__all__ = [
    "normalize_whitespace",
    "standardize_punctuation",
    "strip_diacritics",
    "normalize_for_lookup",
    "build_normalized_index",
    "build_normalized_index_with_collisions",
    "NormalizationOptions",
]

# ---------------------------------------------------------------------------
# Core primitives
# ---------------------------------------------------------------------------

# Matches any run of Unicode whitespace characters.
_WHITESPACE_RE = re.compile(r"\s+")

# A small, conservative set of character replacements to reduce
# common Unicode punctuation variants to stable ASCII equivalents.
_CHAR_TRANSLATION_TABLE = str.maketrans(
    {
        # Apostrophes / quotes
        "’": "'",
        "‘": "'",
        "‛": "'",
        "‚": ",",
        "“": '"',
        "”": '"',
        "„": '"',
        "′": "'",
        "″": '"',
        # Dashes / hyphens
        "–": "-",
        "—": "-",
        "‒": "-",
        "‐": "-",
        "-": "-",
        "﹘": "-",
        "－": "-",
        # Full-width space
        "\u3000": " ",
        # Common separators that often behave like spaces
        "\u00A0": " ",  # NBSP
    }
)

# Zero-width and bidi/control chars that commonly sneak in from copy/paste.
# We remove them to avoid invisible key mismatches.
_STRIP_CODEPOINTS = {
    "\u200B",  # ZERO WIDTH SPACE
    "\u200C",  # ZERO WIDTH NON-JOINER
    "\u200D",  # ZERO WIDTH JOINER
    "\u2060",  # WORD JOINER
    "\uFEFF",  # ZERO WIDTH NO-BREAK SPACE (BOM)
}


def _strip_invisible_controls(text: str) -> str:
    if not text:
        return text
    # Remove known common invisibles first
    for ch in _STRIP_CODEPOINTS:
        if ch in text:
            text = text.replace(ch, "")
    # Remove general "format" category chars (Cf) except those that are
    # meaningful in some scripts. We keep this conservative by only
    # removing if present; this is still deterministic.
    # NOTE: If you later find this too aggressive for a language, make it optional.
    return "".join(ch for ch in text if unicodedata.category(ch) != "Cf")


def normalize_whitespace(text: str) -> str:
    """
    Collapse and trim whitespace in a Unicode-safe way.

    Steps:
      * Unicode NFKC normalization for consistency.
      * Convert all whitespace runs (spaces, tabs, newlines, NBSP, etc.)
        to a single ASCII space ' '.
      * Strip leading and trailing spaces.

    Args:
        text: Raw input string.

    Returns:
        A string with normalized spaces. Empty string for non-strings.
    """
    if not isinstance(text, str):
        return ""

    text = unicodedata.normalize("NFKC", text)
    text = _WHITESPACE_RE.sub(" ", text)
    return text.strip()


def standardize_punctuation(text: str) -> str:
    """
    Map common Unicode punctuation variants to simple ASCII forms.

    Also strips a small set of invisible control characters that can
    lead to hard-to-debug lookup misses.

    Args:
        text: Input string.

    Returns:
        String with punctuation standardized.
    """
    if not isinstance(text, str):
        return ""

    text = unicodedata.normalize("NFKC", text)
    text = _strip_invisible_controls(text)
    return text.translate(_CHAR_TRANSLATION_TABLE)


def strip_diacritics(text: str) -> str:
    """
    Strip combining diacritics while preserving base characters.

    Example:
        'éàï' -> 'eai'

    This is not used by default in `normalize_for_lookup`, because in many
    languages diacritics are semantically important. It is provided as an
    explicit helper for more aggressive matching.

    Args:
        text: Input string.

    Returns:
        A string with combining marks removed. Empty string for non-strings.
    """
    if not isinstance(text, str):
        return ""

    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return unicodedata.normalize("NFC", stripped)


# ---------------------------------------------------------------------------
# Options and public high-level normalizer
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NormalizationOptions:
    """
    Options controlling normalization aggressiveness.

    These defaults match the existing behavior to remain backward-compatible.
    """
    casefold: bool = True
    underscores_to_spaces: bool = True
    standardize_punct: bool = True
    normalize_ws: bool = True
    strip_invisibles: bool = True
    # Off by default: callers must opt-in explicitly.
    strip_marks: bool = False


def normalize_for_lookup(text: str, *, options: Optional[NormalizationOptions] = None) -> str:
    """
    Normalize a lemma / label string into a canonical lookup key.

    Intended for:
      * keys stored in lexicon JSON files
      * user/upstream input used to query those lexica

    Default pipeline (backward-compatible):
      1. Unicode NFKC normalization.
      2. Standardize punctuation (curly quotes, dashes, NBSP, invisibles).
      3. Treat underscores as spaces.
      4. Normalize whitespace (collapse to single spaces, strip edges).
      5. Case-fold (robust lowercasing).

    Optional (opt-in) extras:
      - strip diacritics/combining marks (options.strip_marks=True)

    Args:
        text: Raw lemma or label.
        options: Optional NormalizationOptions.

    Returns:
        Canonical lookup key as a string. Empty string if input is not a
        string or reduces to nothing.
    """
    if not isinstance(text, str):
        return ""

    opts = options or NormalizationOptions()

    # 1. Unicode normalization base
    norm = unicodedata.normalize("NFKC", text)

    # 2. Punctuation / invisibles
    if opts.standardize_punct:
        if opts.strip_invisibles:
            norm = _strip_invisible_controls(norm)
        norm = norm.translate(_CHAR_TRANSLATION_TABLE)
    elif opts.strip_invisibles:
        norm = _strip_invisible_controls(norm)

    # 3. Underscore harmonization
    if opts.underscores_to_spaces:
        norm = norm.replace("_", " ")

    # 4. Whitespace normalization
    if opts.normalize_ws:
        norm = _WHITESPACE_RE.sub(" ", norm).strip()
    else:
        norm = norm.strip()

    if not norm:
        return ""

    # 5. Optional diacritic stripping (aggressive)
    if opts.strip_marks:
        norm = strip_diacritics(norm)
        if opts.normalize_ws:
            norm = _WHITESPACE_RE.sub(" ", norm).strip()
        if not norm:
            return ""

    # 6. Case folding
    if opts.casefold:
        norm = norm.casefold()

    return norm


# ---------------------------------------------------------------------------
# Helpers for building indices
# ---------------------------------------------------------------------------


def build_normalized_index(
    keys: Iterable[str],
    *,
    options: Optional[NormalizationOptions] = None,
) -> Dict[str, str]:
    """
    Build an index from normalized keys to their original forms.

    Collisions:
        First-writer wins (deterministic). For collision details,
        use build_normalized_index_with_collisions().

    Args:
        keys: Iterable of raw key strings.
        options: Optional NormalizationOptions.

    Returns:
        dict {normalized_key -> original_key}
    """
    index: Dict[str, str] = {}
    opts = options or NormalizationOptions()

    for k in keys:
        if not isinstance(k, str):
            continue
        norm = normalize_for_lookup(k, options=opts)
        if not norm:
            continue
        index.setdefault(norm, k)

    return index


def build_normalized_index_with_collisions(
    keys: Iterable[str],
    *,
    options: Optional[NormalizationOptions] = None,
) -> Tuple[Dict[str, str], Dict[str, List[str]]]:
    """
    Build an index and also report collisions.

    Collisions:
        If multiple raw keys normalize to the same normalized key, the index
        keeps the first key (first-writer wins), and collisions records all
        raw keys that mapped to that normalized key.

    Args:
        keys: Iterable of raw key strings.
        options: Optional NormalizationOptions.

    Returns:
        (index, collisions)
        - index: {normalized_key -> chosen_original_key}
        - collisions: {normalized_key -> [all_original_keys_in_order]}
    """
    index: Dict[str, str] = {}
    collisions: Dict[str, List[str]] = {}
    opts = options or NormalizationOptions()

    for k in keys:
        if not isinstance(k, str):
            continue
        norm = normalize_for_lookup(k, options=opts)
        if not norm:
            continue

        if norm not in index:
            index[norm] = k
            collisions[norm] = [k]
        else:
            collisions[norm].append(k)

    # Keep only true collisions (2+ distinct raw keys)
    collisions = {n: ks for n, ks in collisions.items() if len(ks) > 1}
    return index, collisions
