# app\core\domain\constructions\apposition_np.py
# constructions\apposition_np.py
"""
constructions/apposition_np.py

APPOSITION_NP
=============

Abstract pattern (NP-internal):
    HEAD_NP , APPOSITIVE_NP ,

Semantics:
    “X, a Y, …” or “A Y, X, …”, where the appositive NP further describes
    or classifies the head NP:

        - “Marie Curie, a Polish physicist, …”
        - “A Polish physicist, Marie Curie, …”

This construction is responsible for:
    - Building the appositive NP from lemma + features (if no surface override).
    - Choosing order: head-first vs appositive-first.
    - Inserting the commas that mark the appositive.

It does NOT:
    - Build the surrounding clause (copula, verbs, etc.).
    - Handle capitalization beyond simple trimming.

INTERFACES
----------

Slots (input)
-------------

`slots` is a plain dict, e.g.:

    slots = {
        "head": "Marie Curie",          # required: full head NP surface

        # Appositive specification: either surface OR lemma+features+article.
        "appos_surface": None,          # optional full NP override, e.g. "a Polish physicist"
        "appos_lemma": "physicist",     # required if appos_surface is None
        "appos_features": {             # optional, for morphology
            "number": "sg",
            "gender": "f",
            "nationality": "pl",
        },
        "appos_article_type": "indefinite",  # 'indefinite' | 'definite' | 'none'

        # Ordering and punctuation (optional):
        #   position: 'post' (HEAD, APPOS, …) or 'pre' (APPOS, HEAD, …)
        "position": "post",

        # comma_style:
        #   'both'  → "Head, Appos, …"
        #   'after_appos_only' → "Head, Appos …"
        #   'none' → "Head Appos …" (no commas; rare, but available)
        "comma_style": "both",
    }

Language profile
----------------

`lang_profile` is a dict with defaults and language-specific preferences, e.g.:

    lang_profile = {
        "code": "en",

        # Default order if slots["position"] is not set:
        #   'head_appos' or 'appos_head'
        "apposition_np_order": "head_appos",

        # Default comma behavior if slots["comma_style"] is not set:
        #   'both' | 'after_appos_only' | 'none'
        "apposition_commas": "both",

        # Whether articles are used at all:
        "use_articles": True,
    }

Morphology API
--------------

`morph_api` is any object providing at least:

    morph_api.realize_noun(
        lemma: str,
        features: dict,
        lang_profile: dict
    ) -> str

    morph_api.realize_article(
        noun_form: str,
        features: dict,
        article_type: str,
        lang_profile: dict
    ) -> str

If a language does not use articles, `use_articles` should be False or
`realize_article` should return "" for that language.
"""

from typing import Dict, Any


def _get_order(slots: Dict[str, Any], lang_profile: Dict[str, Any]) -> str:
    """
    Decide whether head or appositive comes first.

    Returns:
        'head_appos' or 'appos_head'
    """
    position = slots.get("position")
    if position == "pre":
        return "appos_head"
    if position == "post":
        return "head_appos"

    # Fallback to language default
    return lang_profile.get("apposition_np_order", "head_appos")


def _get_comma_style(slots: Dict[str, Any], lang_profile: Dict[str, Any]) -> str:
    """
    Decide how commas mark the appositive.

    Returns:
        'both' | 'after_appos_only' | 'none'
    """
    style = slots.get("comma_style")
    if style in {"both", "after_appos_only", "none"}:
        return style

    return lang_profile.get("apposition_commas", "both")


def _build_appositive_np(
    slots: Dict[str, Any],
    lang_profile: Dict[str, Any],
    morph_api: Any,
) -> str:
    """
    Build the appositive NP surface string.

    Priority:
        1. If slots["appos_surface"] is provided → use that as-is.
        2. Else, use appos_lemma + appos_features + article-type.
    """
    surface = slots.get("appos_surface")
    if surface:
        return surface.strip()

    lemma = slots.get("appos_lemma")
    if not lemma:
        return ""

    appos_features: Dict[str, Any] = slots.get("appos_features", {}) or {}
    article_type: str = slots.get("appos_article_type", "indefinite")

    noun_form = morph_api.realize_noun(
        lemma=lemma,
        features=appos_features,
        lang_profile=lang_profile,
    ).strip()

    if not noun_form:
        return ""

    if not lang_profile.get("use_articles", True):
        return noun_form

    article_form = morph_api.realize_article(
        noun_form=noun_form,
        features=appos_features,
        article_type=article_type,
        lang_profile=lang_profile,
    ).strip()

    if article_form:
        return f"{article_form} {noun_form}"

    return noun_form


def render(
    slots: Dict[str, Any],
    lang_profile: Dict[str, Any],
    morph_api: Any,
) -> str:
    """
    Render an APPOSITION_NP phrase.

    Typical usage:

        phrase = render(slots, lang_profile, morph_api)
        # e.g. "Marie Curie, a Polish physicist," or "A Polish physicist, Marie Curie,"

    Args:
        slots:        Slot dict as described above.
        lang_profile: Language profile dict.
        morph_api:    Morphology implementation.

    Returns:
        A surface string representing an NP with an appositive, including
        its internal commas but without surrounding clause material.
    """
    head = (slots.get("head") or "").strip()
    if not head:
        # Without a head NP there is no meaningful apposition.
        return ""

    appos = _build_appositive_np(slots, lang_profile, morph_api)
    if not appos:
        # No apposition; just return the head NP.
        return head

    order = _get_order(slots, lang_profile)
    comma_style = _get_comma_style(slots, lang_profile)

    if order == "head_appos":
        # HEAD, APPOS, ...
        if comma_style == "both":
            # "Head, Appos,"
            return f"{head}, {appos},"
        elif comma_style == "after_appos_only":
            # "Head, Appos"
            return f"{head}, {appos}"
        else:  # 'none'
            # "Head Appos"
            return f"{head} {appos}"
    else:
        # 'appos_head' → APPOS, HEAD, ...
        if comma_style == "both":
            # "Appos, Head,"
            return f"{appos}, {head},"
        elif comma_style == "after_appos_only":
            # "Appos, Head"
            return f"{appos}, {head}"
        else:  # 'none'
            # "Appos Head"
            return f"{appos} {head}"
