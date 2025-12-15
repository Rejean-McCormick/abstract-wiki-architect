# constructions\copula_attributive_np.py
"""
constructions/copula_attributive_np.py

COPULA_ATTRIBUTIVE_NP
=====================

Abstract pattern:
    SUBJECT  COPULA  PREDICATE_NP

Semantics:
    “X is (a) Y”, where Y is a *noun* expressing a property / role:
        - “Marie Curie is a Pole.”
        - “Marie Curie is a Catholic.”
        - “The Nile is a river.”

This construction is responsible ONLY for:
    - Choosing the right copula form (including optional zero-copula).
    - Building the predicate NP (article + noun form).
    - Linearizing SUBJECT / COP / PRED_NP according to the language profile.

It does NOT:
    - Do low-level morphology (handled by `morph_api`).
    - Decide on punctuation or capitalization beyond simple trimming.

INTERFACES
----------

Slots (input)
-------------

`slots` is a plain dict with at least:

    slots = {
        "subject": "Marie Curie",              # required, surface string

        "predicate_lemma": "Pole",            # required, lemma of property noun
        "predicate_features": {               # optional, morphosyntactic features
            "number": "sg",
            "gender": "f",
        },

        # Optional, used by morphology:
        "article_type": "indefinite",         # 'indefinite' | 'definite' | 'none'

        # Optional, for copula selection:
        "copula_features": {                  # e.g. tense, polarity, person, number
            "tense": "past",
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
        # Any subset / permutation of ['SUBJ', 'COP', 'PRED_NP']
        "attributive_np_template": ["SUBJ", "COP", "PRED_NP"],

        # Zero-copula behavior:
        "zero_copula": {
            "enabled": True,
            "present_only": True,
        },

        # Articles:
        "use_articles": True,
    }

All keys are optional; sensible defaults are used if missing.

Morphology API
--------------

`morph_api` is any object providing the following methods:

    morph_api.realize_noun(lemma: str, features: dict, lang_profile: dict) -> str
    morph_api.realize_copula(features: dict, lang_profile: dict) -> str
    morph_api.realize_article(
        noun_form: str,
        features: dict,
        article_type: str,
        lang_profile: dict
    ) -> str

Implementations are language/family-specific. If a language does not have
articles or uses an invariant copula, the corresponding methods may return "".
"""

from typing import Dict, Any, List


def _get_template(lang_profile: Dict[str, Any]) -> List[str]:
    """
    Fetch the template for clause linearization.
    Defaults to the canonical S–COP–PRED order.
    """
    default = ["SUBJ", "COP", "PRED_NP"]
    return lang_profile.get("attributive_np_template", default)


def _should_drop_copula(
    copula_form: str,
    copula_features: Dict[str, Any],
    lang_profile: Dict[str, Any],
) -> bool:
    """
    Decide whether to omit the copula (zero-copula construction).

    A basic policy:

        - If `zero_copula.enabled` is False → never drop.
        - If copula_form is empty → effectively dropped.
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


def _build_predicate_np(
    slots: Dict[str, Any],
    lang_profile: Dict[str, Any],
    morph_api: Any,
) -> str:
    """
    Build the predicate NP: (article) + noun form.

    Uses:
        - slots["predicate_lemma"] (required)
        - slots["predicate_features"] (optional)
        - slots["article_type"] (optional, default 'indefinite')

    and calls:
        morph_api.realize_noun(...)
        morph_api.realize_article(...)
    """
    lemma = slots.get("predicate_lemma")
    if not lemma:
        return ""

    predicate_features: Dict[str, Any] = slots.get("predicate_features", {})
    article_type: str = slots.get("article_type", "indefinite")

    noun_form = morph_api.realize_noun(
        lemma=lemma,
        features=predicate_features,
        lang_profile=lang_profile,
    )

    # Articles may be globally disabled for this language.
    if not lang_profile.get("use_articles", True):
        return noun_form

    article_form = morph_api.realize_article(
        noun_form=noun_form,
        features=predicate_features,
        article_type=article_type,
        lang_profile=lang_profile,
    )

    tokens: List[str] = []
    if article_form:
        tokens.append(article_form)
    if noun_form:
        tokens.append(noun_form)

    return " ".join(tokens)


def render(
    slots: Dict[str, Any],
    lang_profile: Dict[str, Any],
    morph_api: Any,
) -> str:
    """
    Render a COPULA_ATTRIBUTIVE_NP clause.

    Args:
        slots:        Slot dict as described in the module docstring.
        lang_profile: Language profile dict.
        morph_api:    Morphology implementation with methods:
                          - realize_noun
                          - realize_copula
                          - realize_article

    Returns:
        A surface string such as:
            "Marie Curie is a Pole."
        (without punctuation; punctuation can be added by a higher layer).
    """
    subject = (slots.get("subject") or "").strip()

    copula_features: Dict[str, Any] = slots.get("copula_features", {})
    copula_form = morph_api.realize_copula(
        features=copula_features,
        lang_profile=lang_profile,
    )

    if _should_drop_copula(copula_form, copula_features, lang_profile):
        copula_form = ""

    predicate_np = _build_predicate_np(slots, lang_profile, morph_api)

    # Map template symbols to actual tokens.
    token_map = {
        "SUBJ": subject,
        "COP": copula_form,
        "PRED_NP": predicate_np,
    }

    ordered_tokens: List[str] = []
    for symbol in _get_template(lang_profile):
        token = token_map.get(symbol, "")
        if token:
            ordered_tokens.append(token)

    return " ".join(ordered_tokens).strip()
