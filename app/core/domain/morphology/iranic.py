# morphology\iranic.py
"""
IRANIC MORPHOLOGY MODULE
------------------------

Morphology helpers for Iranic languages (FA, PS, KU, TG).

This module provides a class-based interface `IranicMorphology` that
wraps language-specific rules from a configuration dictionary.

Responsibilities:
- Ezafe (Izafe) construction: Linking nouns to modifiers (e.g., Persian 'Ketab-e khoob').
- Gender inflection: Applied for languages like Pashto/Kurdish; ignored for Persian.
- Indefinite marking: Handling suffixes like the Persian '-i' (Ya-ye Vahdat).
- Copula selection.

The sentence assembler is *not* defined here; it belongs to a syntax/engine
module which decides on word order.
"""

from __future__ import annotations

from typing import Any, Dict


class IranicMorphology:
    """
    Morphology engine for Iranic languages.
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
        self._morph = config.get("morphology", {})
        self._syntax = config.get("syntax", {})
        self._phonetics = config.get("phonetics", {})
        self._articles = config.get("articles", {})
        self._verbs = config.get("verbs", {})

    def normalize_gender(self, gender: str) -> str:
        """
        Normalize gender to 'male' or 'female'.
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

    def inflect_gender(self, word: str, gender: str) -> str:
        """
        Inflect a word for gender.

        - Persian (fa): Usually returns word unchanged (has_gender=False).
        - Pashto/Kurdish: Applies suffixes based on config.
        """
        target_gender = self.normalize_gender(gender)
        lemma = word.strip()

        # Check if language has gender (defined in JSON syntax section)
        if not self._syntax.get("has_gender", False):
            return lemma

        if target_gender == "male":
            return lemma

        # Apply Suffixes (e.g. Pashto -a for feminine)
        suffixes = self._morph.get("gender_suffixes", [])
        # Sort by length to handle specific endings first
        sorted_suffixes = sorted(
            suffixes, key=lambda x: len(str(x.get("ends_with", ""))), reverse=True
        )

        for rule in sorted_suffixes:
            ending = str(rule.get("ends_with", ""))
            replacement = str(rule.get("replace_with", ""))

            if ending and lemma.endswith(ending):
                return lemma[: -len(ending)] + replacement

        # Generic Fallback
        default = self._morph.get("default_fem_suffix", "")
        if default:
            return lemma + str(default)

        return lemma

    # ------------------------------------------------------------------
    # Ezafe (Linker) Logic
    # ------------------------------------------------------------------

    def apply_ezafe(self, head_noun: str) -> str:
        """
        Apply the Ezafe suffix to a noun if it links to a modifier.

        Logic:
        - If word ends in Vowel -> usage specific suffix (e.g. -ye).
        - If word ends in Consonant -> usage specific suffix (e.g. -e).
        """
        if not head_noun:
            return ""

        # Check if Ezafe is used in this language
        if not self._syntax.get("uses_ezafe", False):
            return head_noun

        # Get vowels list
        vowels = self._phonetics.get("vowels", "aeiou")
        last_char = head_noun[-1].lower()

        # 'Silent h' (heh-ye havvas) often counts as a vowel in Persian phonology
        silent_h_treatment = self._phonetics.get("silent_h_treatment", "consonant")
        is_vowel_ending = last_char in vowels

        if last_char == "h" and silent_h_treatment == "vowel":
            is_vowel_ending = True

        # Determine suffix
        if is_vowel_ending:
            suffix = self._morph.get("ezafe_vowel", "ye")  # e.g. "Daneshmand-e"
        else:
            suffix = self._morph.get("ezafe_consonant", "e")

        # Check if we need a connector (like ZWNJ or hyphen)
        connector = self._syntax.get("ezafe_connector", "-")

        return f"{head_noun}{connector}{suffix}"

    # ------------------------------------------------------------------
    # Indefiniteness
    # ------------------------------------------------------------------

    def apply_indefinite(self, noun_phrase: str) -> str:
        """
        Apply indefinite marker (e.g. Persian 'Ya-ye Vahdat').

        Can be a suffix ('-i') or a prefix particle ('Yek').
        """
        if not noun_phrase:
            return ""

        strategy = self._syntax.get("indefinite_strategy", "none")

        if strategy == "suffix":
            # Add suffix to the end of the phrase
            suffix = self._morph.get("indefinite_suffix", "i")
            return f"{noun_phrase}{suffix}"

        elif strategy == "prefix":
            # Add separate word (e.g. "Yek")
            particle = self._articles.get("indefinite", "")
            if particle:
                return f"{particle} {noun_phrase}"

        return noun_phrase

    # ------------------------------------------------------------------
    # Copula Selection
    # ------------------------------------------------------------------

    def get_copula(self, default: str = "") -> str:
        """
        Get the default copula (e.g. 'ast').
        """
        copula_map = self._verbs.get("copula", {})
        return copula_map.get("default", default)

    # ------------------------------------------------------------------
    # High-Level Helpers
    # ------------------------------------------------------------------

    def render_simple_bio_predicates(
        self, prof_lemma: str, nat_lemma: str, gender: str
    ) -> Dict[str, str]:
        """
        Prepare components for a biography sentence, handling Ezafe chains.

        Returns:
            {
                "profession": <inflected profession noun>,
                "nationality": <inflected nationality adjective>,
                "noun_phrase": <combined "Prof-e Nat" with Ezafe>,
                "copula": <copula verb>
            }
        """
        # 1. Inflect for Gender (if language supports it)
        prof_form = self.inflect_gender(prof_lemma, gender)
        nat_form = self.inflect_gender(nat_lemma, gender)

        # 2. Build the Ezafe chain: Profession links to Nationality
        # "Scientist [of] Polish" -> "Daneshmand-e Lahestani"
        prof_with_ezafe = self.apply_ezafe(prof_form)

        # 3. Combine into Noun Phrase
        # Note: We assume standard "Head-Modifier" order typical of Iranic
        noun_phrase = f"{prof_with_ezafe} {nat_form}"

        # 4. Apply Indefiniteness to the whole group
        # "Daneshmand-e Lahestani-i"
        noun_phrase_final = self.apply_indefinite(noun_phrase)

        copula = self.get_copula()

        return {
            "profession": prof_form,
            "nationality": nat_form,
            "noun_phrase": noun_phrase_final,
            "copula": copula,
        }
