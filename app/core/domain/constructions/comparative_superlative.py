# app\core\domain\constructions\comparative_superlative.py
# constructions\comparative_superlative.py
"""
Comparative / superlative construction.

Language-agnostic pattern for expressing:

    Comparative:
        "X is more/less ADJ than Y."
        "X is ADJ-er than Y."

    Superlative:
        "X is the most/least ADJ (in Z)."
        "X is ADJ-est (among Y)."

This construction delegates:
- NP realization (comparee, standard, domain) to `morph_api.realize_np`.
- Adjective inflection (comparative/superlative) to `morph_api.realize_adjective`.
- Copula inflection to `morph_api.realize_verb`.

It uses templates from `lang_profile` for maximum flexibility.
"""

from typing import Any, Dict, Optional, Union

from .base import BaseConstruction  # expected BaseConstruction interface


NPInput = Union[str, Dict[str, Any]]


class ComparativeSuperlativeConstruction(BaseConstruction):
    """
    Comparative / superlative construction.

    Expected `slots`:

        slots = {
            # Required:
            "comparee": NPInput,       # the thing being described (X)
            "adj_lemma": str,          # adjective lemma (e.g. "famous")
            "degree": str,             # "comparative" | "superlative"

            # Optional:
            "standard": NPInput | None,  # standard of comparison (Y)
            "domain": NPInput | None,    # domain phrase (Z: "in physics", "in history")
            "tense": str = "present",
            "polarity": str = "positive",
            "copula_lemma": str | None,  # override default copula
        }

    `lang_profile` is expected to contain something like:

        {
            "comparative": {
                "template":
                    "{comparee} {copula} {degree_word} {adj} {than_word} {standard}",
                "degree_word": "more",
                "than_word": "than"
            },
            "superlative": {
                "template":
                    "{comparee} {copula} {superlative_word} {adj} {domain}",
                "superlative_word": "the most"
            },
            "copula": {
                "lemma": "be"
            }
        }

    Templates are simple Python `.format` strings with the placeholders:
        - {comparee}
        - {standard}
        - {adj}
        - {copula}
        - {degree_word}
        - {than_word}
        - {superlative_word}
        - {domain}

    Any missing component is replaced by an empty string, and extra spaces
    are normalized.
    """

    id: str = "COMPARATIVE_SUPERLATIVE"

    def realize(
        self,
        slots: Dict[str, Any],
        lang_profile: Dict[str, Any],
        morph_api: Any,
    ) -> str:
        degree = slots.get("degree", "comparative")
        comparee = self._realize_np(slots.get("comparee"), morph_api)
        standard = self._realize_np(slots.get("standard"), morph_api)
        domain = self._realize_np(slots.get("domain"), morph_api)

        adj_surface = self._realize_adjective(slots, degree, morph_api)
        copula_surface = self._realize_copula(slots, lang_profile, morph_api)

        if degree == "superlative":
            return self._realize_superlative(
                comparee=comparee,
                adj=adj_surface,
                domain=domain,
                copula=copula_surface,
                lang_profile=lang_profile,
            )
        else:
            # Default: comparative
            return self._realize_comparative(
                comparee=comparee,
                standard=standard,
                adj=adj_surface,
                copula=copula_surface,
                lang_profile=lang_profile,
            )

    # ------------------------------------------------------------------ #
    # Comparatives
    # ------------------------------------------------------------------ #

    def _realize_comparative(
        self,
        comparee: str,
        standard: str,
        adj: str,
        copula: str,
        lang_profile: Dict[str, Any],
    ) -> str:
        comp_cfg = lang_profile.get("comparative", {})

        template = comp_cfg.get(
            "template",
            "{comparee} {copula} {degree_word} {adj} {than_word} {standard}",
        )
        degree_word = comp_cfg.get("degree_word", "more")
        than_word = comp_cfg.get("than_word", "than")

        # If there is no standard, fall back to a non-contrastive comparative-like
        # structure (e.g. "X is very ADJ" or simply "X is more ADJ").
        if not standard:
            template = comp_cfg.get(
                "template_no_standard",
                "{comparee} {copula} {degree_word} {adj}",
            )

        parts = {
            "comparee": comparee or "",
            "standard": standard or "",
            "adj": adj or "",
            "copula": copula or "",
            "degree_word": degree_word or "",
            "than_word": than_word or "",
            "superlative_word": "",  # unused here
            "domain": "",
        }

        return _normalize_spaces(template.format(**parts))

    # ------------------------------------------------------------------ #
    # Superlatives
    # ------------------------------------------------------------------ #

    def _realize_superlative(
        self,
        comparee: str,
        adj: str,
        domain: str,
        copula: str,
        lang_profile: Dict[str, Any],
    ) -> str:
        sup_cfg = lang_profile.get("superlative", {})

        template = sup_cfg.get(
            "template",
            "{comparee} {copula} {superlative_word} {adj} {domain}",
        )
        superlative_word = sup_cfg.get("superlative_word", "the most")

        # If no domain is provided, templates can omit it:
        if not domain:
            template = sup_cfg.get(
                "template_no_domain",
                "{comparee} {copula} {superlative_word} {adj}",
            )

        parts = {
            "comparee": comparee or "",
            "standard": "",
            "adj": adj or "",
            "copula": copula or "",
            "degree_word": "",
            "than_word": "",
            "superlative_word": superlative_word or "",
            "domain": domain or "",
        }

        return _normalize_spaces(template.format(**parts))

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _realize_np(self, np_spec: Optional[NPInput], morph_api: Any) -> str:
        if not np_spec:
            return ""

        if isinstance(np_spec, str):
            return np_spec

        if isinstance(np_spec, dict):
            if hasattr(morph_api, "realize_np"):
                return morph_api.realize_np(np_spec)
            # Fallback: use lemma or surface
            lemma = np_spec.get("lemma") or np_spec.get("surface") or ""
            return str(lemma)

        return str(np_spec)

    def _realize_adjective(
        self,
        slots: Dict[str, Any],
        degree: str,
        morph_api: Any,
    ) -> str:
        lemma = slots.get("adj_lemma", "")
        if not lemma:
            return ""

        features: Dict[str, Any] = {
            "degree": degree,  # "comparative" or "superlative"
            "polarity": slots.get("polarity", "positive"),
        }

        if hasattr(morph_api, "realize_adjective"):
            return morph_api.realize_adjective(lemma, features)

        # Fallback: simple heuristic for English-like systems
        if degree == "comparative":
            return f"more {lemma}"
        if degree == "superlative":
            return f"most {lemma}"
        return lemma

    def _realize_copula(
        self,
        slots: Dict[str, Any],
        lang_profile: Dict[str, Any],
        morph_api: Any,
    ) -> str:
        tense = slots.get("tense", "present")
        polarity = slots.get("polarity", "positive")

        copula_cfg = lang_profile.get("copula", {})
        copula_lemma = slots.get("copula_lemma") or copula_cfg.get("lemma", "be")

        features: Dict[str, Any] = {
            "tense": tense,
            "polarity": polarity,
            # Agreement features (person/number) could be added here
        }

        if hasattr(morph_api, "realize_verb"):
            return morph_api.realize_verb(copula_lemma, features)

        # Fallback: naive English-like forms
        if tense == "past":
            return "was"
        return "is"


def _normalize_spaces(text: str) -> str:
    """
    Collapse multiple spaces and strip leading/trailing spaces.
    """
    return " ".join(text.split())
