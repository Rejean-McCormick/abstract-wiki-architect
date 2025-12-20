# app\core\domain\morphology\austronesian.py
# morphology\austronesian.py
"""
Austronesian morphology module.

This module encapsulates *only* the word-form logic for Austronesian-type
languages (e.g. Tagalog, Cebuano, Indonesian, Malay, etc.), driven by a
language card such as ``data/austronesian/tl.json``.

Responsibilities (very simplified, configurable):
- Deriving verb forms from lemmas using:
  - voice affixes (actor/patient/locative/etc.),
  - aspect/mode affixes (often with reduplication).
- Deriving simple agent / event nouns via nominalizers.
- Configurable reduplication patterns (full, CV-).

It is deliberately independent from clause-level constructions; higher layers
(constructions/router) should call these methods with abstract features like
{voice="actor", aspect="perfective"} and then decide where to place the
result in the sentence.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class AustronesianMorphology:
    """
    Morphology helper for a single Austronesian language.

    Expected (minimal) JSON schema for the config is something like::

        {
          "morphology": {
            "affixes": {
              "voice": {
                "actor":   {"prefix": "mag", "infix": null, "suffix": null},
                "patient": {"prefix": "i",   "infix": null, "suffix": null}
              },
              "aspect": {
                "imperfective": {
                  "reduplication": "cv",
                  "prefix": null,
                  "suffix": null
                },
                "perfective": {
                  "reduplication": null,
                  "prefix": null,
                  "suffix": null
                }
              },
              "nominalizer": {
                "agent": {"prefix": "ma", "infix": null, "suffix": null},
                "event": {"prefix": "pag", "infix": null, "suffix": null}
              }
            },
            "reduplication": {
              "cv": "cv",
              "full": "full"
            }
          }
        }

    Only the fields actually present in the card are used; missing entries
    fall back to reasonable defaults (i.e. "no marker").
    """

    config: Dict[str, Any]

    # ------------------------------------------------------------------
    # Config helpers
    # ------------------------------------------------------------------

    @property
    def _morph(self) -> Dict[str, Any]:
        return self.config.get("morphology", {}) or {}

    @property
    def _affixes(self) -> Dict[str, Any]:
        return self._morph.get("affixes", {}) or {}

    @property
    def _reduplication(self) -> Dict[str, Any]:
        return self._morph.get("reduplication", {}) or {}

    # ------------------------------------------------------------------
    # Reduplication
    # ------------------------------------------------------------------

    def _redup_cv(self, stem: str) -> str:
        """
        Very simple CV-reduplication:
        - take initial consonant cluster + following vowel (C?V),
        - prepend that to the stem.

        This is a coarse approximation and can be tuned by config later.
        """
        if not stem:
            return stem

        # Find the first vowel
        vowels = "aeiouAEIOU"
        idx = -1
        for i, ch in enumerate(stem):
            if ch in vowels:
                idx = i
                break

        if idx == -1:
            # No vowel → no reduplication
            return stem

        # CV segment is stem[0:idx+1]
        segment = stem[: idx + 1]
        return segment + stem

    def _redup_full(self, stem: str) -> str:
        """
        Full reduplication: stem + stem.
        """
        return stem + stem

    def apply_reduplication(self, stem: str, pattern: Optional[str]) -> str:
        """
        Apply the reduplication pattern to the stem.

        Supported patterns (strings in config):
        - "cv"   : initial CV reduplication
        - "full" : full reduplication
        - None/"" or unknown: no reduplication
        """
        if not pattern:
            return stem

        key = self._reduplication.get(pattern, pattern).lower()

        if key == "cv":
            return self._redup_cv(stem)
        if key == "full":
            return self._redup_full(stem)
        return stem

    # ------------------------------------------------------------------
    # Affix application (prefix / infix / suffix)
    # ------------------------------------------------------------------

    @staticmethod
    def _apply_prefix(prefix: Optional[str], stem: str) -> str:
        if not prefix:
            return stem
        return prefix + stem

    @staticmethod
    def _apply_suffix(suffix: Optional[str], stem: str) -> str:
        if not suffix:
            return stem
        return stem + suffix

    @staticmethod
    def _apply_infix(infix: Optional[str], stem: str) -> str:
        """
        Very simple infix insertion:
        - if infix is None → no change,
        - else insert infix after the first initial consonant (Tagalog-style).

        This is deliberately coarse and language cards can later override
        with more complex rules if needed.
        """
        if not infix or not stem:
            return stem

        vowels = "aeiouAEIOU"
        # Find index of first vowel
        idx = -1
        for i, ch in enumerate(stem):
            if ch in vowels:
                idx = i
                break

        if idx <= 0:
            # No clear initial consonant cluster; just prepend
            return infix + stem

        return stem[:idx] + infix + stem[idx:]

    def _get_affix_spec(self, category: str, key: str) -> Dict[str, Optional[str]]:
        """
        Safely obtain an affix specification for a given category/key:

        - category: "voice", "aspect", "nominalizer", etc.
        - key:      e.g. "actor", "patient", "imperfective", "agent".

        Returns a dict with optional "prefix", "infix", "suffix", and
        optional "reduplication".
        """
        cat_table = self._affixes.get(category, {}) or {}
        spec = cat_table.get(key, {}) or {}
        # Normalize missing keys
        return {
            "prefix": spec.get("prefix"),
            "infix": spec.get("infix"),
            "suffix": spec.get("suffix"),
            # may be absent
            "reduplication": spec.get("reduplication"),
        }

    def apply_affix_spec(self, lemma: str, spec: Dict[str, Optional[str]]) -> str:
        """
        Apply reduplication + prefix/infix/suffix according to a spec dict.

        Order:
        1. reduplication (if any) on the bare lemma,
        2. prefix,
        3. infix,
        4. suffix.
        """
        stem = lemma

        # 1. Reduplication
        red = spec.get("reduplication")
        stem = self.apply_reduplication(stem, red)

        # 2. Prefix
        stem = self._apply_prefix(spec.get("prefix"), stem)

        # 3. Infix
        stem = self._apply_infix(spec.get("infix"), stem)

        # 4. Suffix
        stem = self._apply_suffix(spec.get("suffix"), stem)

        return stem

    # ------------------------------------------------------------------
    # Verb formation
    # ------------------------------------------------------------------

    def make_verb_form(
        self,
        lemma: str,
        *,
        voice: Optional[str] = None,
        aspect: Optional[str] = None,
    ) -> str:
        """
        Build a verb form from a bare lexical root using voice and aspect
        specifications from the config.

        The procedure is:
        - start from lemma,
        - optionally apply voice affix spec,
        - then optionally apply aspect spec (often reduplication-based).

        Parameters
        ----------
        lemma : str
            The bare root (e.g. "sulat" – 'write').
        voice : Optional[str]
            E.g. "actor", "patient", "locative", etc. May be None.
        aspect : Optional[str]
            E.g. "imperfective", "perfective", "contemplative". May be None.

        Returns
        -------
        str
            Surface verb form.
        """
        form = lemma

        # Voice
        if voice:
            v_spec = self._get_affix_spec("voice", voice)
            form = self.apply_affix_spec(form, v_spec)

        # Aspect
        if aspect:
            a_spec = self._get_affix_spec("aspect", aspect)
            form = self.apply_affix_spec(form, a_spec)

        return form

    # ------------------------------------------------------------------
    # Nominalization
    # ------------------------------------------------------------------

    def make_nominalization(
        self,
        lemma: str,
        *,
        nominalizer_type: str = "agent",
    ) -> str:
        """
        Derive a simple noun (agent or event) from a verb or root.

        Parameters
        ----------
        lemma : str
            Base verb/root.
        nominalizer_type : str
            "agent", "event", or other keys defined in
            ``affixes.nominalizer`` in the config.

        Returns
        -------
        str
            Nominalized form.
        """
        spec = self._get_affix_spec("nominalizer", nominalizer_type)
        return self.apply_affix_spec(lemma, spec)

    # ------------------------------------------------------------------
    # Convenience for constructions
    # ------------------------------------------------------------------

    def render_simple_bio_predicates(
        self,
        profession_lemma: str,
        nationality_lemma: Optional[str] = None,
        *,
        voice: str = "actor",
        aspect: str = "perfective",
    ) -> Dict[str, str]:
        """
        Helper tailored to Wikipedia-style bios for Austronesian languages:

        - Profession is often expressed via a nominalization (e.g. "writer",
          "teacher") or as a verb phrase depending on language/style.
          Here we choose a simple agent nominalization of the profession root.
        - Nationality is returned as a bare form, to be placed as needed by
          the construction layer.

        Constructions decide how to combine these (e.g. "Polish writer",
        "writer from Poland"). This function only provides surface chunks.
        """
        profession_noun = self.make_nominalization(
            profession_lemma,
            nominalizer_type="agent",
        )

        result = {"profession": profession_noun}
        if nationality_lemma is not None:
            result["nationality"] = nationality_lemma
        return result


__all__ = ["AustronesianMorphology"]
