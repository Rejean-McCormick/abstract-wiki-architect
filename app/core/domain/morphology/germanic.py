# morphology\germanic.py
"""
morphology/germanic.py

Morphology helpers for Germanic languages (DE, EN, NL, SV, DA, NO).

This module provides a class-based interface `GermanicMorphology` that
wraps language-specific rules from a configuration dictionary.

It is responsible for:

- Profession gender inflection (masc → fem)
- Grammatical gender inference from word shape
- Adjective (nationality) agreement with noun gender
- Indefinite article selection (including English a/an)
- Optional noun capitalization (e.g. German)

The sentence assembler is *not* defined here; it belongs to a syntax/engine
module which decides on word order, copula, punctuation, etc.
"""

from __future__ import annotations

from typing import Any, Dict


class GermanicMorphology:
    """
    Morphology engine for Germanic languages.
    Handles gender, cases (German), and adjective declensions.
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
        self._morph = config.get("morphology", {})
        self._articles = config.get("articles", {})
        self._adj = config.get("adjectives", {})
        self._casing = config.get("casing", {})

    def _get_lang_code(self) -> str:
        """
        Get a stable language code for conditional logic.
        """
        code = self.config.get("code")
        if code:
            return str(code).lower()

        meta = self.config.get("meta", {})
        return str(meta.get("language", "")).lower()

    def normalize_gender(self, gender: str) -> str:
        """
        Normalize a variety of gender labels into 'male' / 'female' / raw.
        """
        if not gender:
            return ""

        g = gender.strip().lower()
        if g in {"f", "female", "woman", "w"}:
            return "female"
        if g in {"m", "male", "man"}:
            return "male"
        return g

    # ------------------------------------------------------------------
    # Noun Morphology
    # ------------------------------------------------------------------

    def inflect_profession(self, lemma: str, gender: str) -> str:
        """
        Inflect a profession lemma for natural gender (typically masc → fem).

        - Uses:
          - config["morphology"]["irregulars"]
          - config["morphology"]["gender_suffixes"]
          - config["morphology"]["generic_feminine_suffix"]
        """
        gender = self.normalize_gender(gender)
        word = lemma.strip()

        # Masculine: assume input lemma is already the correct form.
        if gender == "male":
            return self.apply_casing(word)

        # 1) Irregulars (dictionary lookup, case-insensitive)
        irregulars = self._morph.get("irregulars", {}) or {}
        lowered = word.lower()
        for base, fem in irregulars.items():
            if base.lower() == lowered:
                return self.apply_casing(fem)

        # 2) Suffix rules (e.g. DE: Lehrer → Lehrerin)
        suffixes = self._morph.get("gender_suffixes", []) or []
        # Apply longer endings first (e.g. "-erin" before "-in")
        suffixes_sorted = sorted(
            suffixes, key=lambda r: len(str(r.get("ends_with", ""))), reverse=True
        )

        for rule in suffixes_sorted:
            ending = str(rule.get("ends_with", ""))
            replacement = str(rule.get("replace_with", ""))

            if ending and word.endswith(ending):
                stem = word[: -len(ending)]
                return self.apply_casing(stem + replacement)

        # 3) Generic feminine suffix (e.g. DE: Lehrer → Lehrerin)
        generic_suffix = self._morph.get("generic_feminine_suffix", "")
        if generic_suffix:
            return self.apply_casing(word + str(generic_suffix))

        # 4) Fallback: return lemma unchanged
        return self.apply_casing(word)

    # ------------------------------------------------------------------
    # Grammatical Gender Inference
    # ------------------------------------------------------------------

    def get_grammatical_gender(self, noun_form: str, natural_gender: str) -> str:
        """
        Infer the grammatical gender (m/f/n/pl) of a noun form.

        Uses:
        - config["morphology"]["grammatical_gender_map"]
        - Falls back to natural_gender logic.
        """
        gram_map = self._morph.get("grammatical_gender_map", {}) or {}
        word = noun_form.strip()

        # Check suffix-based map, longest suffix first for safety
        suffixes_sorted = sorted(
            gram_map.items(), key=lambda kv: len(str(kv[0])), reverse=True
        )
        for suffix, gram_gender in suffixes_sorted:
            suffix = str(suffix)
            if suffix and word.endswith(suffix):
                return str(gram_gender)

        # Fallback: approximate from natural gender
        nat = self.normalize_gender(natural_gender)
        defaults = self._morph.get("gender_defaults", "n")

        if nat == "male":
            return "m"
        if nat == "female":
            return "f"

        return defaults

    # ------------------------------------------------------------------
    # Adjective Morphology
    # ------------------------------------------------------------------

    def inflect_adjective(self, lemma: str, grammatical_gender: str) -> str:
        """
        Inflect adjective based on noun gender (Indefinite context).
        """
        adj = lemma.strip()

        if not self._adj.get("inflects", False):
            return adj

        endings = self._adj.get("indefinite_endings", {}) or {}
        suffix = endings.get(grammatical_gender, "")
        return adj + str(suffix)

    # ------------------------------------------------------------------
    # Article Selection
    # ------------------------------------------------------------------

    def get_indefinite_article(self, next_word: str, grammatical_gender: str) -> str:
        """
        Select indefinite article (e.g. a/an, ein/eine, ett/en).
        """
        word = next_word.strip()
        lang = self._get_lang_code()

        # English: a/an logic
        if lang == "en":
            ind = self._articles.get("indefinite", {}) or {}
            phon = self.config.get("phonetics", {}) or {}

            default = ind.get("default", "a")
            vowel_form = ind.get("vowel_trigger", "an")
            vowels = phon.get("vowels", "aeiouAEIOU")

            if not word:
                return default

            first_char = word[0]
            if first_char in vowels:
                return vowel_form
            return default

        # Generic Germanic: lookup by grammatical gender
        ind_map = self._articles.get("indefinite", {}) or {}
        if isinstance(ind_map, str):
            return ind_map

        return ind_map.get(grammatical_gender, ind_map.get("default", ""))

    # ------------------------------------------------------------------
    # Utilities & High-Level
    # ------------------------------------------------------------------

    def apply_casing(self, text: str) -> str:
        """
        Apply language-specific casing (e.g. Capitalize nouns in German).
        """
        if self._casing.get("capitalize_nouns", False) and text:
            return text[0].upper() + text[1:]
        return text

    def realize_verb(self, lemma: str, features: Dict[str, Any]) -> str:
        """
        Simple copula lookup for Germanic bio sentences.
        """
        # We specifically check for common copula lemmas to route to the config
        if lemma in {"be", "sein", "zijn", "vara", "være"}:
            tense = features.get("tense", "present")
            verbs_cfg = self.config.get("verbs", {})
            copula_map = verbs_cfg.get("copula", {})

            # Try to get specific form (e.g. '3sg' for present)
            tense_map = copula_map.get(tense, {})
            if isinstance(tense_map, dict):
                return tense_map.get("3sg", tense_map.get("default", "is"))

            # Fallback if structure is simpler
            return str(tense_map)

        return lemma

    def render_simple_bio_predicates(
        self, profession_lemma: str, nationality_lemma: str, gender: str
    ) -> Dict[str, str]:
        """
        High-level helper for the engine.
        Returns components for: "{NAME} {COPULA} {ARTICLE} {NAT} {PROF}."
        """
        gender_norm = self.normalize_gender(gender)

        # 1. Inflect Profession
        prof_form = self.inflect_profession(profession_lemma, gender_norm)

        # 2. Determine Gender of the WORD (not the person)
        gram_gender = self.get_grammatical_gender(prof_form, gender_norm)

        # 3. Inflect Nationality (adjective)
        nat_form = self.inflect_adjective(nationality_lemma, gram_gender)

        # 4. Select Article (looks at Nationality because it comes first in Germanic: "A German Scientist")
        # Exception: If nat is empty, look at prof.
        target = nat_form if nat_form else prof_form
        article = self.get_indefinite_article(target, gram_gender)

        return {
            "profession": prof_form,
            "nationality": nat_form,
            "article": article,
            "word_gender": gram_gender,
        }
