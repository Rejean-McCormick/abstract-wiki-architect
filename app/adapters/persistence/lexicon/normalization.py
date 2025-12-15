# lexicon\normalization.py
"""
lexicon.normalization
=====================

Utility functions to normalize lemma strings and keys so that
different lexicon files (en/fr/sw/ja) can share a common
lookup strategy.

Goals
-----
- Be tolerant of user input: capitalization, extra spaces,
  different hyphen / apostrophe characters, etc.
- Provide a *stable* canonical form that can be used as a
  dictionary key for lookups and indices.
- Work across scripts (Latin, Cyrillic, CJK, Arabic, …) without
  making language-specific assumptions.

Typical usage
-------------
>>> from lexicon.normalization import normalize_for_lookup
>>> normalize_for_lookup("  Nobel   Prize – in Physics ")
'nobel prize - in physics'

You can use the result as a key into an index built from
lexicon JSON files (e.g., mapping from normalized key to
entry ID / lemma key).
"""

from __future__ import annotations

import re
import unicodedata
from typing import Dict, Iterable

__all__ = [
    "normalize_whitespace",
    "standardize_punctuation",
    "strip_diacritics",
    "normalize_for_lookup",
    "build_normalized_index",
]

# ---------------------------------------------------------------------------
# Core primitives
# ---------------------------------------------------------------------------

# Matches any run of Unicode whitespace characters.
_WHITESPACE_RE = re.compile(r"\s+")

# Characters that should be mapped to simpler ASCII equivalents
# before normalization. This is intentionally small and conservative.
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
        "‐": "-",
        "-": "-",
        "‒": "-",
        # Full-width space
        "\u3000": " ",
    }
)


def normalize_whitespace(text: str) -> str:
    """
    Collapse and trim whitespace in a Unicode-safe way.

    Steps:
      * Convert all whitespace runs (spaces, tabs, newlines, NBSP, etc.)
        to a single ASCII space ' '.
      * Strip leading and trailing spaces.

    Args:
        text: Raw input string.

    Returns:
        A string with normalized spaces.
    """
    if not isinstance(text, str):
        return ""

    # Normalize to a consistent Unicode form first, so that
    # different encodings of the same characters behave identically.
    text = unicodedata.normalize("NFKC", text)
    # Collapse whitespace
    text = _WHITESPACE_RE.sub(" ", text)
    return text.strip()


def standardize_punctuation(text: str) -> str:
    """
    Map common Unicode punctuation variants to simple ASCII forms.

    This avoids issues where, e.g., “Nobel Prize – Physics”
    and "Nobel Prize - Physics" would normalize differently.

    Args:
        text: Input string.

    Returns:
        String with punctuation standardized (curly quotes, en/em-dashes, etc.).
    """
    if not isinstance(text, str):
        return ""

    text = unicodedata.normalize("NFKC", text)
    return text.translate(_CHAR_TRANSLATION_TABLE)


def strip_diacritics(text: str) -> str:
    """
    Strip combining diacritics while preserving base characters.

    Example:
        'éàï' -> 'eai'

    This is *not* used by default in `normalize_for_lookup`, because
    in many languages diacritics are semantically important. It is
    provided as an optional helper for more aggressive matching.

    Args:
        text: Input string.

    Returns:
        A string with combining marks removed.
    """
    if not isinstance(text, str):
        return ""

    # Decompose characters into base + combining marks.
    decomposed = unicodedata.normalize("NFD", text)
    # Drop all combining marks (category "Mn").
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    # Re-compose to NFC to keep things readable.
    return unicodedata.normalize("NFC", stripped)


# ---------------------------------------------------------------------------
# Public high-level normalizer
# ---------------------------------------------------------------------------


def normalize_for_lookup(text: str) -> str:
    """
    Normalize a lemma / label string into a canonical lookup key.

    This function is intended to be used both on:
      * The keys stored in lexicon JSON files
      * The user / upstream input used to query those lexica

    Pipeline:
      1. Unicode NFKC normalization.
      2. Standardize punctuation (curly quotes, dashes, full-width space).
      3. Treat underscores as spaces (so 'nobel_prize_physics' and
         'Nobel Prize – Physics' normalize compatibly).
      4. Normalize whitespace (collapse to single spaces, strip edges).
      5. Case-fold (stronger than lowercasing; handles more scripts).

    We do *not* strip diacritics here – that should be a separate,
    explicit decision via `strip_diacritics` if needed.

    Args:
        text: Raw lemma or label.

    Returns:
        Canonical lookup key as a string. Empty string if input is not
        a string or reduces to nothing.
    """
    if not isinstance(text, str):
        return ""

    # 1. Basic Unicode normalization + punctuation standardisation.
    norm = unicodedata.normalize("NFKC", text)
    norm = standardize_punctuation(norm)

    # 2. Harmonise underscores with spaces. Lexicon keys often
    #    use underscores where human text uses spaces.
    norm = norm.replace("_", " ")

    # 3. Whitespace normalisation.
    norm = normalize_whitespace(norm)

    if not norm:
        return ""

    # 4. Case folding gives more robust matching than simple lower().
    #    It is safe for scripts without case (e.g. CJK).
    norm = norm.casefold()

    return norm


# ---------------------------------------------------------------------------
# Helpers for building indices
# ---------------------------------------------------------------------------


def build_normalized_index(keys: Iterable[str]) -> Dict[str, str]:
    """
    Build a lookup index from *normalized* keys to their original forms.

    This is a convenience helper for lexicon loaders:

        raw_keys = data["professions"].keys()
        index = build_normalized_index(raw_keys)

        def get_profession(key: str):
            norm = normalize_for_lookup(key)
            canonical = index.get(norm)
            if canonical is None:
                return None
            return data["professions"][canonical]

    Collisions:
        If two different raw keys normalize to the same canonical key,
        the *first* one wins and subsequent collisions are ignored.
        In practice, lexica should avoid such ambiguous cases.

    Args:
        keys: Iterable of raw key strings as they appear in JSON.

    Returns:
        A dict {normalized_key -> original_key}.
    """
    index: Dict[str, str] = {}

    for k in keys:
        if not isinstance(k, str):
            continue
        norm = normalize_for_lookup(k)
        if not norm:
            continue
        # First writer wins – keeps behaviour deterministic and simple.
        index.setdefault(norm, k)

    return index
