# app\core\domain\constructions\copula_locative.py
# constructions\copula_locative.py
"""
constructions/copula_locative.py

COPULA_LOCATIVE
================

Abstract pattern:
    SUBJECT  COPULA  LOCATIVE_PHRASE

Semantics:
    “X is in/at/on Y”, where Y is a *location*:

        - “The laboratory is in Paris.”
        - “The statue is at the university.”
        - “The book is on the table.”

This construction is responsible ONLY for:
    - Choosing the right copula form (including optional zero-copula).
    - Building the locative phrase (adposition + location NP, or case-marked NP).
    - Linearizing SUBJECT / COP / LOC according to the language profile.

It does NOT:
    - Perform low-level inflection logic (handled by `morph_api`).
    - Decide on punctuation or capitalization beyond simple trimming.

INTERFACES
----------

Slots (input)
-------------

`slots` is a plain dict with at least:

    slots = {
        "subject": "The laboratory",        # required, surface string (already formed NP)

        # Location as lemma + features, OR a direct surface string:
        "location_lemma": "Paris",          # optional if location_surface given
        "location_features": {              # optional, e.g. case/class/etc.
            "number": "sg",
            "proper": True,
        },
        "location_surface": None,           # optional override: full surface NP

        # Preposition/Adposition semantics:
        "adposition_type": "in",            # 'in' | 'at' | 'on' | 'to' | etc.

        # For copula selection:
        "copula_features": {                # optional, tense/polarity/person/number
            "tense": "present",
            "polarity": "pos",
            "person": 3,
            "number": "sg",
        },
    }

Language profile
----------------

`lang_profile` is a dict with language-level syntactic preferences, e.g.:

    lang_profile = {
        "code": "en",

        # Template for clause-level linearization:
        # Any subset / permutation of ['SUBJ', 'COP', 'LOC_PHRASE']
        "locative_template": ["SUBJ", "COP", "LOC_PHRASE"],

        # Zero-copula behavior:
        "zero_copula": {
            "enabled": False,
            "present_only": True,
        },

        # Whether the language uses adpositions (prep/postp) or prefers
        # pure case marking for location:
        "use_adpositions": True,

        # Order of adposition and location NP (if adpositions are used):
        #   'preposition' → "in Paris"
        #   'postposition' → "Paris-in"
        "locative_adposition_order": "preposition",
    }

All keys are optional; sensible defaults are used if missing.

Morphology API
--------------

`morph_api` is any object providing the following methods:

    morph_api.realize_noun(
        lemma: str,
        features: dict,
        lang_profile: dict
    ) -> str

    morph_api.realize_copula(
        features: dict,
        lang_profile: dict
    ) -> str

    morph_api.realize_adposition(
        adposition_type: str,
        lang_profile: dict
    ) -> str

Implementations are language/family-specific. If a language does not have
adpositions, `realize_adposition` may return "" and `use_adpositions` should be
False so that location is encoded via case or noun class only.
"""

from typing import Dict, Any, List


def _get_template(lang_profile: Dict[str, Any]) -> List[str]:
    """
    Fetch the template for locative clause linearization.
    Defaults to the canonical S–COP–LOC order.
    """
    default = ["SUBJ", "COP", "LOC_PHRASE"]
    return lang_profile.get("locative_template", default)


def _should_drop_copula(
    copula_form: str,
    copula_features: Dict[str, Any],
    lang_profile: Dict[str, Any],
) -> bool:
    """
    Decide whether to omit the copula (zero-copula construction).

    Policy:

        - If copula_form is empty → effectively dropped.
        - If `zero_copula.enabled` is False → never drop.
        - If `present_only` is True:
            drop only when tense is 'present' (or not specified).
    """
    if not copula_form:
        return True

    zero_cfg = lang_profile.get("zero_copula", {})
    if not zero_cfg.get("enabled", False):
        return False

    tense = copula_features.get("tense", "present")
    present_only = zero_cfg.get("present_only", True)

    if present_only and tense != "present":
        return False

    return True


def _build_locative_phrase(
    slots: Dict[str, Any],
    lang_profile: Dict[str, Any],
    morph_api: Any,
) -> str:
    """
    Build the locative phrase.

    Priority:
        1. If slots["location_surface"] is provided → return it as-is.
        2. Else, use location_lemma + location_features + (optional) adposition.

    Uses:
        - slots["location_lemma"]           (optional if surface given)
        - slots["location_features"]        (optional)
        - slots["adposition_type"]          (optional, default 'in')

    and calls:
        morph_api.realize_noun(...)
        morph_api.realize_adposition(...)
    """
    # Direct override: full surface NP for location.
    surface = slots.get("location_surface")
    if surface:
        return surface.strip()

    lemma = slots.get("location_lemma")
    if not lemma:
        return ""

    location_features: Dict[str, Any] = slots.get("location_features", {})
    adposition_type: str = slots.get("adposition_type", "in")

    # Step 1: realize bare location noun (possibly with case or class).
    location_np = morph_api.realize_noun(
        lemma=lemma,
        features=location_features,
        lang_profile=lang_profile,
    ).strip()

    if not location_np:
        return ""

    # Step 2: optionally add adposition (prep/postp) if this language uses them.
    if not lang_profile.get("use_adpositions", True):
        # Location encoded by case or other morphology only.
        return location_np

    adp = morph_api.realize_adposition(
        adposition_type=adposition_type,
        lang_profile=lang_profile,
    ).strip()

    if not adp:
        # No usable adposition returned; fall back to bare location NP.
        return location_np

    order = lang_profile.get("locative_adposition_order", "preposition")
    if order == "postposition":
        # e.g. "Paris-in"
        return f"{location_np} {adp}".strip()

    # Default: preposition (e.g. "in Paris").
    return f"{adp} {location_np}".strip()


def render(
    slots: Dict[str, Any],
    lang_profile: Dict[str, Any],
    morph_api: Any,
) -> str:
    """
    Render a COPULA_LOCATIVE clause.

    Args:
        slots:        Slot dict as described in the module docstring.
        lang_profile: Language profile dict.
        morph_api:    Morphology implementation with methods:
                          - realize_noun
                          - realize_copula
                          - realize_adposition

    Returns:
        A surface string such as:
            "The laboratory is in Paris."
        (without punctuation; punctuation can be added by a higher layer).
    """
    subject = (slots.get("subject") or "").strip()

    copula_features: Dict[str, Any] = slots.get("copula_features", {})
    copula_form = morph_api.realize_copula(
        features=copula_features,
        lang_profile=lang_profile,
    ).strip()

    if _should_drop_copula(copula_form, copula_features, lang_profile):
        copula_form = ""

    loc_phrase = _build_locative_phrase(slots, lang_profile, morph_api)

    token_map = {
        "SUBJ": subject,
        "COP": copula_form,
        "LOC_PHRASE": loc_phrase,
    }

    ordered_tokens: List[str] = []
    for symbol in _get_template(lang_profile):
        token = token_map.get(symbol, "")
        if token:
            ordered_tokens.append(token)

    return " ".join(ordered_tokens).strip()
