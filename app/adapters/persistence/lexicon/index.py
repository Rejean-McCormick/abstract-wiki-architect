# app/adapters/persistence/lexicon/index.py
# lexicon/index.py
"""
lexicon/index.py

Enterprise-grade in-memory index over a `lexicon.types.Lexicon` instance.

Design goals
------------
- No filesystem knowledge (loader handles I/O).
- Deterministic, case-insensitive lookups.
- Optional normalization-based lookups (underscores/spaces/dashes, punctuation),
  without changing the underlying lexicon objects.
- First-writer-wins semantics for index collisions (stable + predictable).
- Minimal surface area: intended for renderers/routers/engines.

Notes
-----
This module does not:
- lemmatize,
- perform fuzzy search,
- call Wikidata.

It provides best-effort lookup across:
- professions
- nationalities
- general entries
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from .types import BaseLexicalEntry, Lexicon, NationalityEntry, ProfessionEntry

try:
    from .normalization import normalize_for_lookup  # type: ignore
except Exception:  # pragma: no cover
    normalize_for_lookup = None  # type: ignore[assignment]


@dataclass
class LexiconIndex:
    """
    Helper around a `Lexicon` that exposes convenient lookups.

    Indices are case-insensitive and best-effort:

      * professions: indexed by key + lemma
      * nationalities: indexed by key + lemma + adjective + demonym + country_name
      * general entries: indexed by key + lemma

    Optional normalization:
      If lexicon.normalization.normalize_for_lookup is available, lookups
      also consider a normalized key (casefold + punctuation/whitespace harmonization)
      for more robust matching.
    """

    lexicon: Lexicon

    def __post_init__(self) -> None:
        self.language: str = self.lexicon.meta.language

        # Internal indices use `str.casefold()` for robust case-insensitive matching.
        self._profession_index: Dict[str, ProfessionEntry] = {}
        self._nationality_index: Dict[str, NationalityEntry] = {}
        self._general_index: Dict[str, BaseLexicalEntry] = {}

        # Optional normalized indices; only populated if normalizer is available.
        self._profession_norm_index: Optional[Dict[str, ProfessionEntry]] = None
        self._nationality_norm_index: Optional[Dict[str, NationalityEntry]] = None
        self._general_norm_index: Optional[Dict[str, BaseLexicalEntry]] = None

        self._build_indices()

    # ------------------------------------------------------------------
    # Normalization helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _norm_casefold(key: str) -> str:
        return key.casefold()

    @staticmethod
    def _norm_lookup(key: str) -> str:
        """
        Best-effort normalized key for lookups.
        Falls back to casefold-only if normalize_for_lookup is unavailable.
        """
        if not isinstance(key, str):
            return ""
        if normalize_for_lookup is None:
            return key.casefold()
        try:
            nk = normalize_for_lookup(key)  # type: ignore[misc]
        except Exception:
            nk = ""
        return (nk or key).casefold()

    def _add_to_index(
        self,
        index: Dict[str, BaseLexicalEntry],
        key: Optional[str],
        entry: BaseLexicalEntry,
    ) -> None:
        """
        Add a mapping to an index using casefold; first-writer-wins.
        """
        if not key:
            return
        k = self._norm_casefold(key)
        if k and k not in index:
            index[k] = entry

    def _add_to_norm_index(
        self,
        index: Dict[str, BaseLexicalEntry],
        key: Optional[str],
        entry: BaseLexicalEntry,
    ) -> None:
        """
        Add a mapping to a normalized index; first-writer-wins.
        """
        if not key:
            return
        k = self._norm_lookup(key)
        if k and k not in index:
            index[k] = entry

    # ------------------------------------------------------------------
    # Index construction
    # ------------------------------------------------------------------

    def _build_indices(self) -> None:
        use_norm = normalize_for_lookup is not None

        if use_norm:
            self._profession_norm_index = {}
            self._nationality_norm_index = {}
            self._general_norm_index = {}

        # Professions: key + lemma
        for entry in self.lexicon.professions.values():
            self._add_to_index(self._profession_index, entry.key, entry)
            self._add_to_index(self._profession_index, entry.lemma, entry)

            if use_norm and self._profession_norm_index is not None:
                self._add_to_norm_index(self._profession_norm_index, entry.key, entry)
                self._add_to_norm_index(self._profession_norm_index, entry.lemma, entry)

        # Nationalities: key + several useful fields
        for entry in self.lexicon.nationalities.values():
            self._add_to_index(self._nationality_index, entry.key, entry)
            self._add_to_index(self._nationality_index, entry.lemma, entry)
            self._add_to_index(self._nationality_index, entry.adjective, entry)
            self._add_to_index(self._nationality_index, entry.demonym, entry)
            self._add_to_index(self._nationality_index, entry.country_name, entry)

            if use_norm and self._nationality_norm_index is not None:
                self._add_to_norm_index(self._nationality_norm_index, entry.key, entry)
                self._add_to_norm_index(self._nationality_norm_index, entry.lemma, entry)
                self._add_to_norm_index(self._nationality_norm_index, entry.adjective, entry)
                self._add_to_norm_index(self._nationality_norm_index, entry.demonym, entry)
                self._add_to_norm_index(self._nationality_norm_index, entry.country_name, entry)

        # General entries: key + lemma
        for entry in self.lexicon.general_entries.values():
            self._add_to_index(self._general_index, entry.key, entry)
            self._add_to_index(self._general_index, entry.lemma, entry)

            if use_norm and self._general_norm_index is not None:
                self._add_to_norm_index(self._general_norm_index, entry.key, entry)
                self._add_to_norm_index(self._general_norm_index, entry.lemma, entry)

    # ------------------------------------------------------------------
    # Public lookup API
    # ------------------------------------------------------------------

    def lookup_profession(self, term: str) -> Optional[ProfessionEntry]:
        """
        Look up a profession by lemma or key, case-insensitive.

        Resolution order:
          1) casefold index
          2) normalized index (if available)
        """
        if not isinstance(term, str) or not term.strip():
            return None

        k = self._norm_casefold(term)
        hit = self._profession_index.get(k)
        if hit is not None:
            return hit

        if self._profession_norm_index is not None:
            return self._profession_norm_index.get(self._norm_lookup(term))

        return None

    def lookup_nationality(self, term: str) -> Optional[NationalityEntry]:
        """
        Look up a nationality by adjective / lemma / key / demonym / country name,
        case-insensitive.

        Resolution order:
          1) casefold index
          2) normalized index (if available)
        """
        if not isinstance(term, str) or not term.strip():
            return None

        k = self._norm_casefold(term)
        hit = self._nationality_index.get(k)
        if hit is not None:
            return hit

        if self._nationality_norm_index is not None:
            return self._nationality_norm_index.get(self._norm_lookup(term))

        return None

    def lookup_any(self, term: str) -> Optional[BaseLexicalEntry]:
        """
        Generic lookup that falls back from professions and nationalities
        to general entries.

        Resolution order:
          1) profession casefold
          2) nationality casefold
          3) general casefold
          4) profession normalized (if available)
          5) nationality normalized (if available)
          6) general normalized (if available)
        """
        if not isinstance(term, str) or not term.strip():
            return None

        k = self._norm_casefold(term)

        prof = self._profession_index.get(k)
        if prof is not None:
            return prof

        nat = self._nationality_index.get(k)
        if nat is not None:
            return nat

        gen = self._general_index.get(k)
        if gen is not None:
            return gen

        nk = self._norm_lookup(term)

        if self._profession_norm_index is not None:
            prof = self._profession_norm_index.get(nk)
            if prof is not None:
                return prof

        if self._nationality_norm_index is not None:
            nat = self._nationality_norm_index.get(nk)
            if nat is not None:
                return nat

        if self._general_norm_index is not None:
            return self._general_norm_index.get(nk)

        return None


__all__ = ["LexiconIndex"]
