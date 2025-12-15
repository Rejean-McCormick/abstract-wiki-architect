# morphology\agglutinative.py
"""
Agglutinative morphology module.

This module encapsulates *only* the word-form logic for agglutinative
languages (Turkish, Hungarian, Finnish, Estonian, etc.), driven by a
language card such as ``data/agglutinative/tr.json``.

Responsibilities:
- Vowel harmony classification.
- Selection of suffix variants (plural, copula, question, …).
- Simple chaining of suffixes to form predicates (e.g. “öğrenci” → “öğrencidir”).

It is deliberately independent from clause-level constructions; higher layers
(constructions/router) should call these methods with abstract features.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional


@dataclass
class AgglutinativeMorphology:
    """
    Morphology helper for a single agglutinative language.

    The expected JSON schema matches cards like ``data/agglutinative/tr.json``,
    i.e.::

        {
          "phonetics": {
            "vowels": "aeıioöuüAEIİOÖUÜ",
            "default_vowel": "a",
            "harmony_groups": {
              "back": ["a", "ı", "o", "u"],
              "front": ["e", "i", "ö", "ü"],
              ...
            }
          },
          "morphology": {
            "suffixes": {
              "plural": {
                "back": "lar",
                "front": "ler",
                "default": "lar"
              },
              "copula": {
                "back_unrounded": "dır",
                "front_unrounded": "dir",
                ...
              },
              ...
            },
            "buffer_consonant": "y"  # optional
          }
        }

    Only the fields actually present in the card are used; missing entries
    fall back to reasonable defaults.
    """

    config: Dict[str, Any]

    # ------------------------------------------------------------------
    # Basic phonetic helpers
    # ------------------------------------------------------------------

    @property
    def _vowels(self) -> str:
        return self.config.get("phonetics", {}).get("vowels") or "aeiouAEIOU"

    @property
    def _default_vowel(self) -> str:
        return self.config.get("phonetics", {}).get("default_vowel") or "a"

    @property
    def _harmony_groups(self) -> Dict[str, Iterable[str]]:
        return self.config.get("phonetics", {}).get("harmony_groups", {}) or {}

    @property
    def _suffix_rules(self) -> Dict[str, Dict[str, str]]:
        return self.config.get("morphology", {}).get("suffixes", {}) or {}

    @property
    def _buffer_consonant(self) -> str:
        """
        Optional buffer consonant when a vowel-final stem meets a
        vowel-initial suffix (very simplified model).
        """
        return self.config.get("morphology", {}).get("buffer_consonant", "")

    # ------------------------------------------------------------------
    # Harmony core
    # ------------------------------------------------------------------

    def get_last_vowel(self, word: str) -> str:
        """
        Return the last vowel of ``word`` according to the language's
        vowel inventory. If no vowel is found, fall back to the configured
        default vowel.

        Examples (Turkish):
            "öğrenci" -> "i"
            "okul"    -> "u"
        """
        vowels = self._vowels
        for ch in reversed(word):
            if ch.lower() in vowels:
                return ch.lower()
        return self._default_vowel.lower()

    def get_harmony_group(self, vowel: str) -> Optional[str]:
        """
        Map a vowel to its harmony group name, e.g. "back", "front",
        "back_unrounded", "front_rounded", etc., as defined in the card.

        Returns ``None`` if the vowel does not belong to any group.
        """
        vowel = vowel.lower()
        for group_name, group_vowels in self._harmony_groups.items():
            if vowel in group_vowels:
                return group_name
        return None

    # ------------------------------------------------------------------
    # Suffix selection and application
    # ------------------------------------------------------------------

    def choose_suffix_variant(self, stem: str, suffix_type: str) -> str:
        """
        Choose the appropriate allomorph for a given ``suffix_type`` based
        on the stem's last vowel and the configured harmony groups.

        If no matching group variant is found, falls back to the
        suffix's "default" variant, or the empty string.
        """
        suffixes_by_type = self._suffix_rules
        if suffix_type not in suffixes_by_type:
            return ""

        stem_vowel = self.get_last_vowel(stem)
        group_name = self.get_harmony_group(stem_vowel)
        variants = suffixes_by_type[suffix_type]

        # Direct match on group name (e.g. "front", "back_unrounded", …)
        if group_name and group_name in variants:
            return variants[group_name]

        # Best-effort fallback
        return variants.get("default", "")

    def _needs_buffer(self, stem: str, suffix: str) -> bool:
        """
        Decide whether to insert a buffer consonant between ``stem`` and
        ``suffix``. Very coarse prototype: only checks vowel-vowel clash.
        """
        if not stem or not suffix:
            return False
        if not self._buffer_consonant:
            return False

        vowels = self._vowels
        return stem[-1].lower() in vowels and suffix[0].lower() in vowels

    def attach_suffix(self, stem: str, suffix_type: str) -> str:
        """
        Attach a single suffix of type ``suffix_type`` to ``stem``,
        respecting (simplified) buffer consonant rules.

        Returns the new form; ``stem`` is not modified in place.
        """
        allomorph = self.choose_suffix_variant(stem, suffix_type)
        if not allomorph:
            return stem

        if self._needs_buffer(stem, allomorph):
            return stem + self._buffer_consonant + allomorph
        return stem + allomorph

    def apply_suffix_chain(self, root: str, suffix_types: Iterable[str]) -> str:
        """
        Apply a sequence of suffix types to ``root`` in order, returning
        the final surface form.

        Example (TR-style):
            apply_suffix_chain("öğrenci", ["plural", "copula"])
        """
        form = root
        for s_type in suffix_types:
            form = self.attach_suffix(form, s_type)
        return form

    # ------------------------------------------------------------------
    # Higher-level helpers used by constructions
    # ------------------------------------------------------------------

    def make_plural(self, noun_lemma: str) -> str:
        """
        Return the plural form of the noun, if a 'plural' suffix is
        configured, otherwise the lemma itself.
        """
        return self.attach_suffix(noun_lemma, "plural")

    def make_predicative_noun(
        self,
        noun_lemma: str,
        *,
        add_copula: bool = True,
        add_question_particle: bool = False,
    ) -> str:
        """
        Turn a bare noun lemma into a predicative form ("is a NOUN"),
        typically by attaching a copular suffix and optionally a
        question particle.

        Parameters
        ----------
        noun_lemma:
            Base noun (e.g. profession).
        add_copula:
            Whether to attach a copula suffix (e.g. -dır).
        add_question_particle:
            Whether to attach a question particle suffix (e.g. mı/mi/mu/mü).

        Returns
        -------
        str
            Surface form with requested suffixes attached.
        """
        suffix_chain = []
        if add_copula and "copula" in self._suffix_rules:
            suffix_chain.append("copula")
        if add_question_particle and "question" in self._suffix_rules:
            suffix_chain.append("question")

        if not suffix_chain:
            return noun_lemma

        return self.apply_suffix_chain(noun_lemma, suffix_chain)

    # ------------------------------------------------------------------
    # Convenience entry point mirroring old engine behaviour
    # ------------------------------------------------------------------

    def render_simple_predicate(
        self,
        profession_lemma: str,
        nationality_lemma: str,
    ) -> Dict[str, str]:
        """
        Small helper that mimics the old agglutinative engine's behaviour
        for Wikipedia-style bios:

        - Returns a predicative profession form ("öğrencidir").
        - Leaves nationality as a bare modifier (adjective or noun).

        The caller (construction layer) is responsible for ordering and
        inserting into a sentence template.
        """
        pred_prof = self.make_predicative_noun(profession_lemma, add_copula=True)
        return {
            "profession": pred_prof,
            "nationality": nationality_lemma,
        }


__all__ = ["AgglutinativeMorphology"]
