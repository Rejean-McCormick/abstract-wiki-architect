# app\core\domain\morphology\dravidian.py
# morphology\dravidian.py
"""
Dravidian morphology module.

This module encapsulates *only* the word-form logic for Dravidian-type
languages (e.g. Tamil, Telugu, Kannada, Malayalam), driven by a language
card such as ``data/dravidian/ta.json``.

Responsibilities:
- Number marking (plural).
- Simple case marking on nouns.
- Person/number/gender agreement on copular or auxiliary suffixes.
- Very light, configurable sandhi.

It is deliberately independent from clause-level constructions; higher layers
(constructions/router) should call these methods with abstract features like
{case="dat", number="pl", person=3, gender="f", tense="pres", …}.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class DravidianMorphology:
    """
    Morphology helper for a single Dravidian language.

    Expected (minimal) JSON schema for the config is something like::

        {
          "morphology": {
            "suffixes": {
              "plural": "gal",
              "oblique": "in",
              "case": {
                "nom": "",
                "acc": "ai",
                "dat": "ukku",
                "loc": "il",
                "gen": "in"
              },
              "copula": {
                "present": {
                  "3sg_masc": "aan",
                  "3sg_fem": "aal",
                  "3sg_neut": "adu",
                  "3pl": "aargal"
                },
                "past": {
                  "3sg_masc": "aanaan",
                  "3sg_fem": "aaval",
                  "3sg_neut": "aayitatu",
                  "3pl": "aargal"
                }
              }
            },
            "order": {
              "plural_before_case": true
            },
            "sandhi": {
              "drop_final_u_before_vowel_suffix": true
            }
          }
        }

    Only the fields actually present in the card are used; missing entries
    fall back to reasonable defaults.
    """

    config: Dict[str, Any]

    # ------------------------------------------------------------------
    # Config helpers
    # ------------------------------------------------------------------

    @property
    def _morph(self) -> Dict[str, Any]:
        return self.config.get("morphology", {}) or {}

    @property
    def _suffixes(self) -> Dict[str, Any]:
        return self._morph.get("suffixes", {}) or {}

    @property
    def _order(self) -> Dict[str, Any]:
        return self._morph.get("order", {}) or {}

    @property
    def _sandhi(self) -> Dict[str, Any]:
        return self._morph.get("sandhi", {}) or {}

    @property
    def _plural_suffix(self) -> str:
        return str(self._suffixes.get("plural", ""))

    # ------------------------------------------------------------------
    # Sandhi (very light, configurable)
    # ------------------------------------------------------------------

    def _apply_sandhi(self, stem: str, suffix: str) -> str:
        """
        Very simple, opt-in sandhi rules controlled by config.

        Currently supported:
        - drop_final_u_before_vowel_suffix: drop stem-final 'u' if suffix
          begins with a vowel (Tamil-style pattern).
        """
        if not stem or not suffix:
            return stem + suffix

        s_cfg = self._sandhi
        result_stem = stem

        if s_cfg.get("drop_final_u_before_vowel_suffix", False):
            if stem.endswith(("u", "U")) and suffix[0].lower() in "aeiouāīūēō":
                result_stem = stem[:-1]

        return result_stem + suffix

    # ------------------------------------------------------------------
    # Noun morphology: number + case
    # ------------------------------------------------------------------

    def _attach_suffix(self, stem: str, suffix: str) -> str:
        """
        Attach a raw suffix to a stem, running any sandhi rules.
        """
        if not suffix:
            return stem
        return self._apply_sandhi(stem, suffix)

    def make_plural(self, noun_lemma: str, number: str) -> str:
        """
        Return the appropriately numbered noun form.

        Parameters
        ----------
        noun_lemma : str
            Base noun lemma.
        number : {"sg","pl",...}
            Grammatical number. If not "pl", the lemma is returned unchanged.
        """
        if number != "pl" or not self._plural_suffix:
            return noun_lemma
        return self._attach_suffix(noun_lemma, self._plural_suffix)

    def _get_case_suffix(self, case: str) -> str:
        """
        Get the case suffix string for a given abstract case label.
        Unknown cases default to the bare form (no suffix).
        """
        case_table = self._suffixes.get("case", {}) or {}
        return str(case_table.get(case, ""))

    def make_noun_form(
        self,
        lemma: str,
        *,
        number: str = "sg",
        case: str = "nom",
    ) -> str:
        """
        Create a fully inflected noun form with number and case.

        The order of plural vs case suffix is controlled by the
        ``order.plural_before_case`` flag in the config. Some Dravidian
        languages attach plural before case; others may vary.

        Parameters
        ----------
        lemma : str
            Base noun lemma.
        number : str
            "sg" or "pl".
        case : str
            Abstract case label: "nom", "acc", "dat", "loc", "gen", etc.

        Returns
        -------
        str
            Surface form with requested morphology.
        """
        plural_first = bool(self._order.get("plural_before_case", True))
        form = lemma

        case_suffix = self._get_case_suffix(case)

        if plural_first:
            form = self.make_plural(form, number)
            form = self._attach_suffix(form, case_suffix)
        else:
            form = self._attach_suffix(form, case_suffix)
            form = self.make_plural(form, number)

        return form

    # ------------------------------------------------------------------
    # Copula / agreement morphology
    # ------------------------------------------------------------------

    def _copula_table_for_tense(self, tense: str) -> Dict[str, str]:
        """
        Return the copula suffix table for a given tense.

        Config structure::

            "copula": {
              "present": {"3sg_masc": "...", ...},
              "past": {"3sg_masc": "...", ...}
            }

        Unknown tense → {} (no copula).
        """
        cop = self._suffixes.get("copula", {}) or {}
        return cop.get(tense, {}) or {}

    @staticmethod
    def _agreement_key(
        person: int,
        number: str,
        gender: Optional[str],
    ) -> str:
        """
        Build a key like "1sg", "2pl", "3sg_masc" for table lookup.
        """
        base = f"{person}{number}"
        if person == 3 and gender:
            # normalize gender to a short, lowercase label
            g = gender.lower()
            if g.startswith("m"):
                return base + "_masc"
            if g.startswith("f"):
                return base + "_fem"
            if g.startswith("n"):
                return base + "_neut"
        return base

    def get_copula_suffix(
        self,
        *,
        tense: str = "present",
        person: int = 3,
        number: str = "sg",
        gender: Optional[str] = None,
    ) -> str:
        """
        Return a copular/auxiliary suffix according to agreement features.

        If no matching entry is found, returns the empty string.
        """
        table = self._copula_table_for_tense(tense)
        key = self._agreement_key(person, number, gender)
        return str(table.get(key, ""))

    def make_predicative_noun(
        self,
        noun_lemma: str,
        *,
        person: int = 3,
        number: str = "sg",
        gender: Optional[str] = None,
        tense: str = "present",
        include_copula: bool = True,
    ) -> str:
        """
        Turn a bare noun lemma into a predicative "X is NOUN" form by
        attaching an agreement-sensitive copula/auxiliary suffix.

        Example (Tamil-style configuration, very simplified):
            lemma="āciriyar" (teacher)  →
            "āciriyaraan"  ("he is a teacher")
            "āciriyaraal"  ("she is a teacher")

        The actual shapes depend entirely on the JSON card.

        Parameters
        ----------
        noun_lemma : str
            Base noun lemma.
        person, number, gender, tense
            Agreement features for the copula suffix.
        include_copula : bool
            If False, return the bare noun (useful for zero-copula contexts).

        Returns
        -------
        str
            Surface form with optional copular suffix.
        """
        if not include_copula:
            return noun_lemma

        cop_suffix = self.get_copula_suffix(
            tense=tense, person=person, number=number, gender=gender
        )
        if not cop_suffix:
            return noun_lemma

        return self._attach_suffix(noun_lemma, cop_suffix)

    # ------------------------------------------------------------------
    # Convenience for constructions
    # ------------------------------------------------------------------

    def render_simple_bio_predicates(
        self,
        profession_lemma: str,
        nationality_lemma: Optional[str] = None,
        *,
        person: int = 3,
        number: str = "sg",
        gender: Optional[str] = None,
        tense: str = "past",
    ) -> Dict[str, str]:
        """
        Helper tailored to Wikipedia-style bios:
        - Return a predicative profession form with copular suffix.
        - Return nationality as a bare modifier (left to constructions).

        Constructions decide ordering (e.g. "Polish physicist" vs "physicist from Poland").
        """
        profession_pred = self.make_predicative_noun(
            profession_lemma,
            person=person,
            number=number,
            gender=gender,
            tense=tense,
            include_copula=True,
        )

        result = {"profession": profession_pred}
        if nationality_lemma is not None:
            result["nationality"] = nationality_lemma
        return result


__all__ = ["DravidianMorphology"]
