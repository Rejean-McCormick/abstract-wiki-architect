# app\core\domain\morphology\celtic.py
# morphology\celtic.py
"""
Celtic morphology helpers.

This module provides data-driven utilities for Celtic languages
(e.g. Welsh, Irish, Scottish Gaelic, Breton), based on per-language
JSON configuration files under something like data/celtic/*.json.

It does NOT decide sentence order or construction choice; it only
handles:

- Optional gender-based derivation of nouns/adjectives (if the language uses it).
- Initial consonant mutations (soft, lenition, eclipsis, etc.), via config.
- Simple copula form selection for a given tense/person/number.
- A convenience helper for biographical predicates (profession + nationality).

Everything is driven by configuration so that individual languages can
encode as much or as little morphology as needed.
"""

from __future__ import annotations
from typing import Dict, Any, Optional


class CelticMorphology:
    """
    Morphology engine for Celtic languages.
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
        self._morph = config.get("morphology", {})
        self._mutations = self._morph.get("mutations", {})
        self._syntax = config.get("syntax", {})
        self._verbs = config.get("verbs", {})

    # ---------------------------------------------------------------------------
    # Generic helpers
    # ---------------------------------------------------------------------------

    def _apply_suffix_rules(self, word: str, rules: Any) -> str:
        """
        Apply the first matching suffix replacement rule to `word`.

        Rules are expected to be a list of dicts:
        [{ "ends_with": "...", "replace_with": "..." }, ...]
        """
        if not isinstance(rules, list):
            return word

        # Match longer endings first
        sorted_rules = sorted(
            rules,
            key=lambda r: len(r.get("ends_with", "")),
            reverse=True,
        )

        for rule in sorted_rules:
            end = rule.get("ends_with", "")
            repl = rule.get("replace_with", "")
            if end and word.endswith(end):
                stem = word[: -len(end)]
                return stem + repl

        return word

    def _apply_initial_mutation(self, word: str, mutation_rules: Any) -> str:
        """
        Apply an initial consonant mutation to `word` according to `mutation_rules`.

        `mutation_rules` is expected to be a list of dicts:
        [{ "from": "p", "to": "ph" }, { "from": "c", "to": "ch" }, ...]

        The function matches the longest prefix first, so it can handle
        multi-letter clusters like "gw" or "bh".
        """
        if not isinstance(mutation_rules, list):
            return word

        word = (word or "").strip()
        if not word:
            return word

        # Sort by length of "from" to prefer longer clusters
        sorted_rules = sorted(
            mutation_rules,
            key=lambda r: len(r.get("from", "")),
            reverse=True,
        )

        for rule in sorted_rules:
            src = rule.get("from", "")
            dst = rule.get("to", "")
            if src and word.startswith(src):
                return dst + word[len(src) :]

        return word

    def apply_mutation(self, word: str, mutation_name: Optional[str]) -> str:
        """
        Apply a named initial mutation to `word` (e.g. 'soft', 'lenition', 'eclipsis').

        The config is expected to contain:
        config['morphology']['mutations'][mutation_name] -> list of rules

        If mutation_name is None, empty, or not configured, the word is returned unchanged.
        """
        word = (word or "").strip()
        if not word:
            return word

        if not mutation_name:
            return word

        rules = self._mutations.get(mutation_name)

        if not rules:
            return word

        return self._apply_initial_mutation(word, rules)

    # ---------------------------------------------------------------------------
    # Gender derivation (if applicable)
    # ---------------------------------------------------------------------------

    def genderize_noun(self, lemma: str, gender: str) -> str:
        """
        Return the nominative form of a profession/role noun for the given natural gender.

        Many Celtic languages do NOT regularly derive feminine forms via suffixes,
        so often this simply returns the lemma.

        The config can override this with:
        config['morphology']['gender_inflection']['noun_suffixes'] -> rules
        config['morphology']['irregulars'] -> {lemma: feminine_form}
        """
        lemma = (lemma or "").strip()
        gender = (gender or "").lower().strip()

        # Only try to change form for female if rules/irregulars are defined.
        if gender != "female":
            return lemma

        irregulars = self._morph.get("irregulars", {})

        if lemma in irregulars:
            return irregulars[lemma]

        noun_rules = self._morph.get("gender_inflection", {}).get("noun_suffixes", [])
        if noun_rules:
            return self._apply_suffix_rules(lemma, noun_rules)

        # Default: no change
        return lemma

    def genderize_adjective(self, lemma: str, gender: str) -> str:
        """
        Return the nominative form of a nationality adjective for the given natural gender.

        Many Celtic languages do not mark gender on adjectives, but some may.
        The config can specify:
        config['morphology']['gender_inflection']['adjective_suffixes'] -> rules
        config['morphology']['irregulars'] -> {lemma: feminine_form}
        """
        lemma = (lemma or "").strip()
        gender = (gender or "").lower().strip()

        if gender != "female":
            return lemma

        irregulars = self._morph.get("irregulars", {})

        if lemma in irregulars:
            return irregulars[lemma]

        adj_rules = self._morph.get("gender_inflection", {}).get(
            "adjective_suffixes", []
        )
        if adj_rules:
            return self._apply_suffix_rules(lemma, adj_rules)

        return lemma

    # ---------------------------------------------------------------------------
    # Copula selection
    # ---------------------------------------------------------------------------

    def select_copula(
        self,
        tense: str,
        person: int,
        number: str,
    ) -> str:
        """
        Select the correct copula form for the given tense/person/number.

        The config is expected to contain:

        config['verbs']['copula'] = {
            "present": {
            "1sg": "...",
            "2sg": "...",
            "3sg": "...",
            "1pl": "...",
            "2pl": "...",
            "3pl": "...",
            "default": "..."
            },
            "past": { ... },
            ...
        }

        The `number` should be 'sg' or 'pl'.
        If the specific form is missing, falls back to 'default' for that tense,
        and finally to an empty string.
        """
        copula_cfg = self._verbs.get("copula", {})

        tense = (tense or "present").lower().strip()
        number = (number or "sg").lower().strip()

        person_key = f"{person}{number}"  # e.g. "3sg"
        tense_map = copula_cfg.get(tense, {})

        if not isinstance(tense_map, dict):
            return ""

        form = tense_map.get(person_key)
        if form is not None:
            return form

        # Fallback to tense-level default if present
        return tense_map.get("default", "")

    # ---------------------------------------------------------------------------
    # High-level helper for a typical biographical predicate
    # ---------------------------------------------------------------------------

    def render_simple_bio_predicates(
        self,
        prof_lemma: str,
        nat_lemma: str,
        gender: str,
    ) -> Dict[str, str]:
        """
        Convenience function for biographical sentences in Celtic languages.

        Tasks:

        1. Derive gender-appropriate nominative forms for:
            - profession (noun)
            - nationality (adjective or noun)
        2. Apply predicative initial mutations as configured:
            - e.g. soft mutation after a feminine noun, or after 'yn' in Welsh.
        3. Select a default copula form for a simple 3sg statement.

        The config may contain:

        config['syntax'] = {
            "bio_tense": "present" | "past" | ...,
            "predicative_mutation_profession": "soft" | "lenition" | null,
            "predicative_mutation_nationality": "soft" | "lenition" | null
        }

        Returns a dict:

        {
            "profession": <mutated_profession>,
            "nationality": <mutated_nationality>,
            "copula": <copula_form>,
            "tense": <tense_used>
        }
        """
        gender_norm = (gender or "").lower().strip()

        bio_tense = self._syntax.get("bio_tense", "present")
        mut_prof = self._syntax.get("predicative_mutation_profession")
        mut_nat = self._syntax.get("predicative_mutation_nationality")

        # 1. Nominative / base forms by gender
        prof_nom = self.genderize_noun(prof_lemma, gender_norm)
        nat_nom = self.genderize_adjective(nat_lemma, gender_norm)

        # 2. Apply initial mutations if configured
        prof_inf = self.apply_mutation(prof_nom, mut_prof)
        nat_inf = self.apply_mutation(nat_nom, mut_nat)

        # 3. Copula (3rd person singular is typical for bios: "he/she is/was")
        copula = self.select_copula(bio_tense, person=3, number="sg")

        return {
            "profession": prof_inf,
            "nationality": nat_inf,
            "copula": copula,
            "tense": bio_tense,
        }
