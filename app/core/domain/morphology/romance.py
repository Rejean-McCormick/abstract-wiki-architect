# morphology\romance.py
"""
ROMANCE MORPHOLOGY LAYER
------------------------

Shared morphology helpers for Romance languages (it, es, fr, pt, ro, ca, …).

This module provides a class-based interface `RomanceMorphology` that
wraps language-specific rules from a configuration dictionary.

It is responsible for:
- Inflecting gendered lemmas using suffix rules + irregular maps.
- Selecting indefinite articles based on phonetic triggers.

The sentence assembler is *not* defined here; it belongs to a syntax/engine
module which decides on word order, copula, punctuation, etc.
"""

from __future__ import annotations

from typing import Any, Dict, Literal, Tuple

Gender = Literal["male", "female"]

_ROMANCE_VOWELS = "aeiouàèìòùáéíóúâêîôûAEIOUÀÈÌÒÙÁÉÍÓÚÂÊÎÔÛ"


class RomanceMorphology:
    """
    Morphology engine for Romance languages.
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
        self._morph = config.get("morphology", {})
        self._articles = config.get("articles", {})
        self._phonetics = config.get("phonetics", {})

    def _normalize_gender(self, gender: str) -> Gender:
        """
        Normalize a free-form gender string into 'male' or 'female'.

        Anything that is not clearly 'female' is treated as 'male', because
        Romance profession lemmas are conventionally stored in masculine form.
        """
        g = (gender or "").strip().lower()
        if g in {"f", "female", "fem", "woman", "w"}:
            return "female"
        return "male"

    def _preserve_capitalisation(self, original: str, inflected: str) -> str:
        """
        Preserve leading capitalisation from the original lemma.

        Example:
            original='Italiano', inflected='italiana' -> 'Italiana'
        """
        if not original:
            return inflected
        if original[0].isupper() and inflected:
            return inflected[0].upper() + inflected[1:]
        return inflected

    def inflect_gendered_lemma(
        self,
        lemma: str,
        gender: str,
    ) -> str:
        """
        Inflect a profession/nationality lemma for grammatical gender.

        Args:
            lemma: Base lemma (usually masculine singular), e.g. 'attore', 'italiano'.
            gender: Target gender ('Male'/'Female'/variants).

        Returns:
            The inflected surface form (string).
        """
        norm_gender = self._normalize_gender(gender)
        base = (lemma or "").strip()
        if not base:
            return base

        # If we are asked for masculine, we generally return the lemma as is.
        if norm_gender == "male":
            return base

        # Work in lowercase for rule matching.
        lower = base.lower()
        irregulars: Dict[str, str] = self._morph.get("irregulars", {}) or {}

        # 1. Irregular dictionary lookup
        if lower in irregulars:
            candidate = irregulars[lower]
            return self._preserve_capitalisation(base, candidate)

        # 2. Suffix rules (ordered, longest first for safety)
        suffixes = self._morph.get("suffixes", []) or []
        # Be defensive: ignore malformed entries.
        valid_suffixes = [
            r
            for r in suffixes
            if isinstance(r, dict)
            and "ends_with" in r
            and "replace_with" in r
            and isinstance(r["ends_with"], str)
            and isinstance(r["replace_with"], str)
        ]
        # More specific endings should be tried first.
        valid_suffixes.sort(key=lambda r: len(r["ends_with"]), reverse=True)

        for rule in valid_suffixes:
            ending = rule["ends_with"]
            replacement = rule["replace_with"]

            if ending and lower.endswith(ending):
                stem = lower[: -len(ending)]
                candidate = stem + replacement
                return self._preserve_capitalisation(base, candidate)

        # 3. Generic Romance fallback: -o → -a
        if lower.endswith("o"):
            candidate = lower[:-1] + "a"
            return self._preserve_capitalisation(base, candidate)

        # 4. No applicable rule: return lemma unchanged
        return base

    def select_indefinite_article(
        self,
        next_word: str,
        gender: str,
    ) -> str:
        """
        Pick the correct indefinite article before `next_word`.

        Args:
            next_word: The word that follows the article (already inflected).
            gender: Target gender ('Male'/'Female'/variants).

        Returns:
            The indefinite article string (may be empty if not configured).
        """
        norm_gender = self._normalize_gender(gender)

        word = (next_word or "").strip()
        if not word:
            # No following word; fall back to a bare default if possible.
            bucket = "m" if norm_gender == "male" else "f"
            rules = self._articles.get(bucket, {})
            return rules.get("default", "")

        gender_key = "m" if norm_gender == "male" else "f"
        rules: Dict[str, Any] = self._articles.get(gender_key, {}) or {}
        default_article: str = rules.get("default", "")

        if not rules:
            return ""

        # 1. Vowel-initial words (elision, l'/un', etc.)
        if word[0] in _ROMANCE_VOWELS:
            vowel_form = rules.get("vowel")
            if vowel_form:
                return vowel_form

        # 2. Impure / complex onsets (Italian specific)
        # Config example:
        # "impure_triggers": ["s_consonant", "z", "gn", "ps"]
        impure_triggers = self._phonetics.get("impure_triggers", []) or []
        if impure_triggers:
            is_s_consonant = (
                word.startswith("s")
                and len(word) > 1
                and word[1] not in _ROMANCE_VOWELS
            )

            # any other clusters like z-, gn-, ps-, etc.
            other_match = any(
                t != "s_consonant" and word.startswith(t) for t in impure_triggers
            )

            if (is_s_consonant and "s_consonant" in impure_triggers) or other_match:
                s_impure_form = rules.get("s_impure")
                if s_impure_form:
                    return s_impure_form

        # 3. Spanish-style stressed-A nouns (águila, agua…)
        stressed_a_words = self._phonetics.get("stressed_a_words", []) or []
        # We compare in lowercase for robustness.
        if word.lower() in {w.lower() for w in stressed_a_words}:
            stressed_form = rules.get("stressed_a")
            if stressed_form:
                return stressed_form

        # 4. Default article
        return default_article

    def render_simple_bio_predicates(
        self,
        prof_lemma: str,
        nat_lemma: str,
        gender: str,
    ) -> Tuple[str, str, str, str]:
        """
        High-level helper for the engine.

        Returns:
            (article, profession_form, nationality_form, sep)
        """
        # Normalise lemmas for rule lookup, but keep original for case recovery.
        prof_inflected = self.inflect_gendered_lemma(prof_lemma, gender)
        nat_inflected = self.inflect_gendered_lemma(nat_lemma, gender)

        article = self.select_indefinite_article(prof_inflected, gender)

        # If article ends with an apostrophe, we do not want a space afterwards.
        if article and article.endswith("'"):
            sep = ""
        else:
            # Default: single space between article and profession.
            sep = " "

        return article, prof_inflected, nat_inflected, sep
