# app\core\domain\morphology\indo_aryan.py
# morphology\indo_aryan.py
"""
INDO-ARYAN MORPHOLOGY MODULE
----------------------------

Morphology helpers for Indo-Aryan languages (HI, BN, UR, PA, MR, etc.).

This module provides a class-based interface `IndoAryanMorphology` that
wraps language-specific rules from a configuration dictionary.

Responsibilities:
- Gender inflection for nouns and adjectives (e.g. Hindi: larka -> larki).
- Handling of zero-copula features (e.g. Bengali present tense).
- Honorific agreement for verbs/copulas.
- Suffix replacement based on phonetics/orthography.

This module is stateless; all rules come from the `config` object.
"""

from __future__ import annotations

from typing import Any, Dict


class IndoAryanMorphology:
    """
    Morphology engine for Indo-Aryan languages.
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
        self._morph = config.get("morphology", {})
        self._syntax = config.get("syntax", {})
        self._verbs = config.get("verbs", {})

    def normalize_gender(self, gender: str) -> str:
        """
        Normalize gender to 'male' or 'female'.
        Default to 'male' if unknown, as it is typically the base form.
        """
        if not gender:
            return "male"
        g = gender.strip().lower()
        if g in {"f", "female", "fem", "woman"}:
            return "female"
        return "male"

    # ------------------------------------------------------------------
    # Gender Inflection
    # ------------------------------------------------------------------

    def inflect_gender(
        self, word: str, gender: str, part_of_speech: str = "noun"
    ) -> str:
        """
        Inflect a word (noun or adjective) for the target natural gender.

        - Checks syntax flags (e.g. `adjective_gender_agreement`).
        - Checks irregulars.
        - Applies suffix replacement rules.
        """
        target_gender = self.normalize_gender(gender)
        lemma = word.strip()

        # If target is male, usually return base (unless we add specific male rules later)
        if target_gender == "male":
            return lemma

        # Check if this POS inflects for gender in this language
        # e.g. Bengali adjectives usually don't, Hindi ones do.
        # Default to True if config is missing.
        agreement_key = f"{part_of_speech}_gender_agreement"
        if not self._syntax.get(agreement_key, True):
            return lemma

        # 1. Irregulars
        irregulars = self._morph.get("irregulars", {})
        # Case-insensitive check
        for base, fem in irregulars.items():
            if base.lower() == lemma.lower():
                return fem

        # 2. Suffix Rules
        # Expected format: [{"ends_with": "aa", "replace_with": "ii"}, ...]
        suffixes = self._morph.get("suffixes", [])
        # Sort by length descending to match longest suffix first
        sorted_suffixes = sorted(
            suffixes, key=lambda x: len(str(x.get("ends_with", ""))), reverse=True
        )

        for rule in sorted_suffixes:
            ending = str(rule.get("ends_with", ""))
            replacement = str(rule.get("replace_with", ""))

            if ending and lemma.endswith(ending):
                return lemma[: -len(ending)] + replacement

        # 3. Generic Fallback (Hindi/Urdu style heuristic)
        # If no rule matched, and it ends in 'aa', try 'ii'.
        # This is a safe default for many IA languages if rules are missing.
        if lemma.endswith("aa"):
            return lemma[:-2] + "ii"

        # If word ends in 'a' (short), sometimes it changes to 'i'
        if lemma.endswith("a") and not lemma.endswith("aa"):
            # This assumes strict transliteration; might need tuning per language
            return lemma[:-1] + "i"

        return lemma

    # ------------------------------------------------------------------
    # Copula Selection
    # ------------------------------------------------------------------

    def get_copula(self, gender: str, formality: str = "formal") -> str:
        """
        Select the appropriate copula (verb 'to be').

        Handles:
        - Zero copula (e.g. Bengali present tense).
        - Honorifics (formal vs informal).
        - Gender agreement (e.g. Marathi/Hindi past tense).
        """
        copula_defs = self._verbs.get("copula", {})
        target_gender = self.normalize_gender(gender)

        # 1. Zero Copula check
        if copula_defs.get("zero_copula_in_present", False):
            return ""

        # 2. Formality / Honorifics
        # "formal" is often the default for encyclopedic text
        if formality in copula_defs:
            return copula_defs[formality]

        # 3. Gendered Copula
        # Some languages have gendered copulas (e.g. Hindi 'tha' vs 'thi' in past)
        # Assuming the config might have "male"/"female" keys
        if target_gender in copula_defs:
            return copula_defs[target_gender]

        # 4. Default
        return copula_defs.get("default", "")

    # ------------------------------------------------------------------
    # High-Level Helpers
    # ------------------------------------------------------------------

    def render_simple_bio_predicates(
        self, prof_lemma: str, nat_lemma: str, gender: str
    ) -> Dict[str, str]:
        """
        Prepare the predicate components for a biography sentence.

        Returns:
            {
                "profession": <inflected profession noun>,
                "nationality": <inflected nationality adjective>,
                "copula": <copula verb>
            }
        """
        # Inflect Profession (Noun)
        prof_form = self.inflect_gender(prof_lemma, gender, part_of_speech="noun")

        # Inflect Nationality (Adjective)
        nat_form = self.inflect_gender(nat_lemma, gender, part_of_speech="adjective")

        # Get Copula (Formal by default for bios)
        copula = self.get_copula(gender, formality="formal")

        return {"profession": prof_form, "nationality": nat_form, "copula": copula}
