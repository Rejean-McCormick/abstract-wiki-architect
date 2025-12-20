# app\core\domain\constructions\copula_equative_simple.py
# constructions\copula_equative_simple.py
"""
constructions/copula_equative_simple.py

A family-agnostic construction module for the simple equative pattern:

    X is Y

This construction expresses **class membership / identity** with a copula:

    - "Marie Curie is a physicist."
    - "Python is a programming language."

It does **not** implement morphology itself. Instead, it delegates all
word-form and NP-building logic to a `morph_api` object.

Expected responsibilities:

- This module:
    - Decides *whether* to use an overt copula (zero vs non-zero).
    - Decides shallow *ordering* of SUBJ / COP / PRED.
    - Assembles the linear sequence of surface strings.

- `morph_api`:
    - Builds the subject NP surface form.
    - Builds the predicate NP surface form.
    - Inflects and returns the copula form.

- `lang_profile`:
    - Encodes language-specific parameters for copula behavior and word order.

--------------------
INTERFACES
--------------------

1. abstract_slots (dict)

Minimal expected shape (you can add more fields as needed):

    abstract_slots = {
        "subject": {
            # at minimum:
            "name": "Marie Curie",
            # optional:
            "person": 3,
            "number": "sg",
            "features": {...}  # anything your morph API wants
        },
        "predicate": {
            # free-form structure; passed directly to morph_api:
            # e.g. profession/nationality info
            "role": "profession+nationality",
            "profession_lemma": "physicist",
            "nationality_lemma": "polish",
            "gender": "female",
            "features": {...}
        },
        "tense": "present",  # or "past", "future", etc.
        # optional:
        "polarity": "affirmative"  # reserved for future use
    }

2. lang_profile (dict)

Recommended keys (you can extend this):

    lang_profile = {
        "language_code": "en",

        "copula": {
            "lemma": "be",

            # zero-copula flags (equative/attributive present):
            "present_zero": False,
            "past_zero": False,

            # basic position/word order for this construction:
            # supported values:
            #   "S-COP-PRED"
            #   "S-PRED"        (used when copula is always zero)
            #   "PRED-COP-S"    (some languages / stylistic variants)
            "order": "S-COP-PRED",
        }
    }

3. morph_api (object)

This module expects that `morph_api` exposes three methods:

    - realize_subject(subject_data: dict, lang_profile: dict) -> str
    - realize_predicate(predicate_data: dict, lang_profile: dict) -> str
    - realize_copula(
          tense: str,
          subject_data: dict,
          lang_profile: dict
      ) -> str

All three methods should return **surface strings** (already inflected,
with any required internal spacing handled by the morph layer).

--------------------
RETURN VALUE
--------------------

The main entry point is `realize`, which returns:

    {
        "tokens":   [ "Marie Curie", "is", "a Polish physicist" ],
        "text":     "Marie Curie is a Polish physicist",
        "subject":  "Marie Curie",
        "copula":   "is",
        "predicate":"a Polish physicist"
    }

The caller can then drop `"text"` directly into a larger sentence,
or further process the `"tokens"` if needed.
"""

from typing import Any, Dict, List


def _get_tense(abstract_slots: Dict[str, Any]) -> str:
    """
    Helper: extract tense from abstract slots with a sensible default.
    """
    tense = abstract_slots.get("tense", "present")
    if not isinstance(tense, str):
        return "present"
    return tense.lower()


def _copula_is_zero(tense: str, lang_profile: Dict[str, Any]) -> bool:
    """
    Decide whether the copula should be **zero** for this tense
    in this language profile.

    Uses:

        lang_profile["copula"]["present_zero"]  (bool)
        lang_profile["copula"]["past_zero"]     (bool)

    You can extend this logic as needed (e.g. conditional, future, etc.).
    """
    cop_cfg = (
        (lang_profile.get("copula") or {})
        if isinstance(lang_profile.get("copula"), dict)
        else {}
    )

    if tense == "present":
        return bool(cop_cfg.get("present_zero", False))
    if tense == "past":
        return bool(cop_cfg.get("past_zero", False))

    # Default: no zero-copula
    return False


def _get_order(lang_profile: Dict[str, Any], copula_zero: bool) -> str:
    """
    Resolve the linearization order for this construction.

    If a zero-copula is enforced, we can simplify "S-COP-PRED" → "S-PRED".
    """
    cop_cfg = (
        (lang_profile.get("copula") or {})
        if isinstance(lang_profile.get("copula"), dict)
        else {}
    )

    order = cop_cfg.get("order") or "S-COP-PRED"
    order = str(order).upper().replace(" ", "")

    if copula_zero and order == "S-COP-PRED":
        return "S-PRED"

    # Only support a small, explicit set of patterns for this simple
    # equative construction. More exotic patterns belong to a different
    # construction (e.g. topic-comment).
    if order in {"S-COP-PRED", "S-PRED", "PRED-COP-S"}:
        return order

    # Fallback
    return "S-COP-PRED" if not copula_zero else "S-PRED"


def realize(
    abstract_slots: Dict[str, Any],
    lang_profile: Dict[str, Any],
    morph_api: Any,
) -> Dict[str, Any]:
    """
    Realize a simple copular equative clause of the form:

        SUBJECT (COPULA) PREDICATE

    This construction intentionally ignores topic-marking, focus movement,
    or additional adverbials; those belong to other constructions.

    Parameters
    ----------
    abstract_slots:
        Dict describing at least "subject", "predicate", and optionally "tense".
    lang_profile:
        Language-specific configuration for copula behavior and word order.
    morph_api:
        Object exposing:
            - realize_subject(...)
            - realize_predicate(...)
            - realize_copula(...)

    Returns
    -------
    Dict with:
        - "tokens":   list of surface tokens (already spaced at the phrase level)
        - "text":     single surface string
        - "subject":  subject NP string
        - "copula":   copula string (possibly "")
        - "predicate":predicate NP string
    """
    subject_data = abstract_slots.get("subject", {}) or {}
    predicate_data = abstract_slots.get("predicate", {}) or {}

    # 1. Tense and zero-copula decision
    tense = _get_tense(abstract_slots)
    copula_zero = _copula_is_zero(tense, lang_profile)

    # 2. Realize subject and predicate via morphology API
    subject_str = morph_api.realize_subject(subject_data, lang_profile)
    predicate_str = morph_api.realize_predicate(predicate_data, lang_profile)

    subject_str = subject_str.strip()
    predicate_str = predicate_str.strip()

    # 3. Realize copula (if not zero)
    if copula_zero:
        copula_str = ""
    else:
        copula_str = morph_api.realize_copula(tense, subject_data, lang_profile).strip()

    # 4. Determine linear order
    order = _get_order(lang_profile, copula_zero)

    tokens: List[str] = []

    if order == "S-PRED":
        # SUBJECT PREDICATE
        if subject_str:
            tokens.append(subject_str)
        if predicate_str:
            tokens.append(predicate_str)

    elif order == "PRED-COP-S":
        # PREDICATE COPULA SUBJECT
        if predicate_str:
            tokens.append(predicate_str)
        if copula_str:
            tokens.append(copula_str)
        if subject_str:
            tokens.append(subject_str)

    else:  # default "S-COP-PRED"
        # SUBJECT COPULA PREDICATE
        if subject_str:
            tokens.append(subject_str)
        if copula_str:
            tokens.append(copula_str)
        if predicate_str:
            tokens.append(predicate_str)

    # Remove any accidental empties and extra whitespace in tokens
    tokens = [t.strip() for t in tokens if t and t.strip()]

    # Join with single spaces; punctuation (if needed) should be added by the
    # caller or a higher-level clause-assembly layer.
    text = " ".join(tokens)

    return {
        "tokens": tokens,
        "text": text,
        "subject": subject_str,
        "copula": copula_str,
        "predicate": predicate_str,
    }
