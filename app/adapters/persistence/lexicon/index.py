# lexicon\index.py
"""
lexicon/index.py

Lightweight in-memory index over a `lexicon.types.Lexicon` instance.

This is deliberately small and runtime-oriented:

    - it does NOT know about JSON files or the filesystem
      (see `lexicon.loader` for that),
    - it builds case-insensitive indices over professions,
      nationalities and general entries,
    - it provides a tiny lookup API used by engines / routers.

Typical usage (see qa/test_lexicon_index.py):

    from lexicon.loader import load_lexicon
    from lexicon.index import LexiconIndex

    lex = load_lexicon("it")   # returns lexicon.types.Lexicon
    index = LexiconIndex(lex)

    prof = index.lookup_profession("fisico")
    nat  = index.lookup_nationality("italiano")
    any_ = index.lookup_any("scienziato")
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from .types import (
    BaseLexicalEntry,
    Lexicon,
    NationalityEntry,
    ProfessionEntry,
)


@dataclass
class LexiconIndex:
    """
    Small helper around a `Lexicon` that exposes convenient lookups.

    The index is **case-insensitive** and best-effort:

      * professions are indexed by both key and lemma,
      * nationalities are indexed by key, lemma, adjective, demonym,
        and country_name (when present),
      * general entries are indexed by key and lemma and are only
        consulted as a fallback via `lookup_any`.

    It does not perform lemmatisation, fuzzy search, or Wikidata lookups.
    """

    lexicon: Lexicon

    def __post_init__(self) -> None:
        self.language: str = self.lexicon.meta.language

        # Internal indices use `str.casefold()` for robust
        # case-insensitive matching.
        self._profession_index: Dict[str, ProfessionEntry] = {}
        self._nationality_index: Dict[str, NationalityEntry] = {}
        self._general_index: Dict[str, BaseLexicalEntry] = {}

        self._build_indices()

    # ------------------------------------------------------------------
    # Index construction
    # ------------------------------------------------------------------

    @staticmethod
    def _norm(key: str) -> str:
        """Normalise a lookup key for case-insensitive matching."""
        return key.casefold()

    def _add_to_index(
        self,
        index: Dict[str, BaseLexicalEntry],
        key: Optional[str],
        entry: BaseLexicalEntry,
    ) -> None:
        """
        Add a (key -> entry) mapping to an index, if key is truthy and
        not already present (first writer wins).
        """
        if not key:
            return
        norm = self._norm(key)
        if norm not in index:
            index[norm] = entry  # keep first occurrence

    def _build_indices(self) -> None:
        # Professions: key + lemma
        for entry in self.lexicon.professions.values():
            self._add_to_index(self._profession_index, entry.key, entry)
            self._add_to_index(self._profession_index, entry.lemma, entry)

        # Nationalities: key + several useful fields
        for entry in self.lexicon.nationalities.values():
            self._add_to_index(self._nationality_index, entry.key, entry)
            self._add_to_index(self._nationality_index, entry.lemma, entry)
            self._add_to_index(self._nationality_index, entry.adjective, entry)
            self._add_to_index(self._nationality_index, entry.demonym, entry)
            self._add_to_index(self._nationality_index, entry.country_name, entry)

        # General entries: key + lemma
        for entry in self.lexicon.general_entries.values():
            self._add_to_index(self._general_index, entry.key, entry)
            self._add_to_index(self._general_index, entry.lemma, entry)

    # ------------------------------------------------------------------
    # Public lookup API (used in tests and by engines)
    # ------------------------------------------------------------------

    def lookup_profession(self, term: str) -> Optional[ProfessionEntry]:
        """
        Look up a profession by lemma or key, case-insensitive.

        Examples (with the Italian test fixture):

            index.lookup_profession("fisico")   -> ProfessionEntry
            index.lookup_profession("FISICO")   -> same entry
        """
        return self._profession_index.get(self._norm(term))  # type: ignore[return-value]

    def lookup_nationality(self, term: str) -> Optional[NationalityEntry]:
        """
        Look up a nationality entry by adjective / lemma / key / demonym /
        country name, case-insensitive.
        """
        return self._nationality_index.get(self._norm(term))  # type: ignore[return-value]

    def lookup_any(self, term: str) -> Optional[BaseLexicalEntry]:
        """
        Generic lookup that falls back from professions and nationalities
        to general entries.

        Resolution order:

            1. profession index
            2. nationality index
            3. general entries
        """
        norm = self._norm(term)

        prof = self._profession_index.get(norm)
        if prof is not None:
            return prof

        nat = self._nationality_index.get(norm)
        if nat is not None:
            return nat

        return self._general_index.get(norm)


__all__ = ["LexiconIndex"]
