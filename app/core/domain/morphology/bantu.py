# app\core\domain\morphology\bantu.py
# morphology\bantu.py
"""
BANTU MORPHOLOGY MODULE
-----------------------
Noun-class based morphology utilities for Bantu languages (e.g. Swahili).

This module is responsible ONLY for:
- Choosing the right noun/adjective prefixes for a given noun class.
- Applying simple vowel-harmony adjustments to those prefixes.
- Selecting a class-specific copula (if defined).

Sentence-level assembly (word order, punctuation, etc.) is handled elsewhere
by construction modules. This file is purely about *forms*, not full sentences.

It expects a JSON configuration shaped like data/bantu/sw.json in this repo.
"""

from typing import Any, Dict


class BantuMorphology:
    """
    Morphology engine for Bantu languages.
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
        self._morph = config.get("morphology", {})
        self._syntax = config.get("syntax", {})
        self._verbs = config.get("verbs", {})

    def get_default_human_class(self) -> str:
        """
        Return the default noun class to use for human singular subjects.

        Many Bantu languages use:
        - Class 1 for human singular (e.g. m- / mu-)
        - Class 2 for human plural (e.g. wa-)

        The config is expected to provide:
            config["syntax"]["default_human_class"]

        If missing, falls back to "1".
        """
        return str(self._syntax.get("default_human_class", "1"))

    def _get_prefix_maps(self):
        """
        Internal helper to fetch noun and adjective prefix maps
        from the morphology section of the config.
        """
        prefixes = self._morph.get("prefixes", {})
        adjective_prefixes = self._morph.get("adjective_prefixes", prefixes)
        return prefixes, adjective_prefixes

    def apply_class_prefix(
        self,
        word: str,
        target_class: str,
        word_type: str = "noun",
    ) -> str:
        """
        Attach the appropriate class prefix to a noun or adjective.

        Args:
            word:       Lemma or stem for the lexical item (e.g. 'walimu', 'zuri').
            target_class: Noun class identifier as a string (e.g. "1", "2", "9").
            word_type: Either 'noun' or 'adjective'. Adjectives can use a separate
                       concord prefix map if provided.

        Returns:
            The inflected form with the appropriate class prefix, e.g.:
                'alimu' + class-1 → 'mwalimu'
                'zuri'  + class-1 adjective → 'mzuri'
        """
        if not word:
            return word

        prefixes, adjective_prefixes = self._get_prefix_maps()

        # 1. Class-specific base prefix
        target_prefix = prefixes.get(target_class, "")

        # 2. Whole-word irregular overrides
        irregulars = self._morph.get("irregulars", {})
        if word in irregulars:
            return irregulars[word]

        # 3. Use adjective concord if requested
        if word_type == "adjective":
            target_prefix = adjective_prefixes.get(target_class, target_prefix)

        # NOTE ON STEMMING:
        # In a full system you would strip any existing dictionary prefix to get
        # the true stem (e.g. 'mwalimu' → 'alimu'). For this prototype we assume
        # that:
        # - Inputs are either stems or
        # - The irregular map handles common dictionary forms.
        # We therefore do *not* strip prefixes automatically.

        # 4. Vowel-based allomorphy for prefixes (simple harmony)
        #    e.g. Swahili: m- → mw- before vowel; wa- → w- before vowel.
        vowel_rules = self._morph.get("vowel_harmony", {})
        if word and word[0].lower() in "aeiou" and target_prefix in vowel_rules:
            target_prefix = vowel_rules[target_prefix]

        return f"{target_prefix}{word}"

    def inflect_noun_for_class(
        self,
        lemma: str,
        noun_class: str,
    ) -> str:
        """
        Convenience wrapper: inflect a noun lemma for a given noun class.

        Typically used for professions or other head nouns in bios.
        """
        lemma = lemma.strip()
        if not lemma:
            return lemma
        return self.apply_class_prefix(lemma, noun_class, word_type="noun")

    def inflect_adjective_for_class(
        self,
        lemma: str,
        noun_class: str,
    ) -> str:
        """
        Convenience wrapper: inflect an adjective lemma for a given noun class.

        Typically used for nationalities or descriptive adjectives that must
        agree with a class-1 human subject, etc.
        """
        lemma = lemma.strip()
        if not lemma:
            return lemma
        return self.apply_class_prefix(lemma, noun_class, word_type="adjective")

    def get_copula_for_class(
        self,
        noun_class: str,
    ) -> str:
        """
        Return a copular form agreeing with the given noun class, if available.

        The config is expected to define something like:

            "verbs": {
              "copula": {
                "default": "ni",
                "1": "yu",
                "2": "wa"
              }
            }

        For Swahili, for example, 'ni' is often invariant, but other Bantu
        languages may have class-specific copulas.
        """
        copula_map = self._verbs.get("copula", {})

        # Class-specific copula (if provided)
        if noun_class in copula_map:
            return copula_map[noun_class]

        # Invariant fallback
        return copula_map.get("default", "")

    def get_human_singular_bundle(
        self,
        prof_lemma: str,
        nat_lemma: str,
    ) -> Dict[str, str]:
        """
        High-level helper: given profession & nationality lemmas,
        return their class-1 (human singular) forms plus the matching copula.

        This is a convenience for construction modules that want to say
        things like:
            {NAME} {COPULA} {PROF} {NAT}

        Returns a dict with keys:
            - 'class': noun class used (string, e.g. "1")
            - 'profession': inflected profession
            - 'nationality': inflected nationality
            - 'copula': class-agreeing copula (or default/invariant)
        """
        human_class = self.get_default_human_class()

        inflected_prof = self.inflect_noun_for_class(prof_lemma, human_class)
        inflected_nat = self.inflect_adjective_for_class(nat_lemma, human_class)
        copula = self.get_copula_for_class(human_class)

        return {
            "class": human_class,
            "profession": inflected_prof,
            "nationality": inflected_nat,
            "copula": copula,
        }
