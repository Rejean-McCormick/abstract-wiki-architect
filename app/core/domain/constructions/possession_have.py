# app\core\domain\constructions\possession_have.py
# constructions\possession_have.py
"""
POSSESSION_HAVE CONSTRUCTION
----------------------------

Language-family-agnostic construction for possessive clauses of the form:

    "X has Y."

Examples:
    - "Marie Curie has two daughters."
    - "The city has many museums."

This construction is responsible for:

    - Choosing the linear order of POSSESSOR, VERB("have"), POSSESSED.
    - Passing the right role/feature information to the morphology layer.
    - Optionally allowing focus/fronting of the possessed NP (via pattern).

It is *not* responsible for:

    - Inflecting the verb ("have") for tense, person, number, polarity.
    - Internal morphology of NPs (plural, classifiers, gender, etc.).
    - Encoding alternative possession strategies ("to X there is Y" style).
      Those should use a different construction (e.g. POSSESSION_EXISTENTIAL).

Those tasks are delegated to the morphology / language-specific layer
via the `morph_api` object.

----------------------------------------------------------------------
EXPECTED INPUTS
----------------------------------------------------------------------

Slots (first argument: `slots`)

A dictionary with at least:

    {
        "possessor": {
            "lemma": str,
            "features": dict   # optional, can be empty
        },
        "possessed": {
            "lemma": str,
            "features": dict   # optional
        },
        "tense": "pres" | "past" | "fut" | ... (optional, default "pres"),
        "polarity": "pos" | "neg"          (optional, default "pos")
    }

Language profile (second argument: `lang_profile`)

A dictionary providing construction-specific parameters. Suggested keys:

    "possession_have": {
        "pattern": "subj_verb_obj"
                    | "subj_obj_verb"
                    | "verb_subj_obj"
                    | "obj_verb_subj",
        "verb_lemma": str  # e.g. "have", "avoir", "tener"
    }

If omitted, defaults are chosen as:

    pattern    = "subj_verb_obj"
    verb_lemma = "have"

Morph API (third argument: `morph_api`)

An object providing at least the following methods:

    morph_api.realize_np(sem: dict, role: str, features: dict | None) -> str
        - sem: the NP semantics (contains "lemma" and optionally more)
        - role: a label such as "possessor" or "possessed"
        - features: morphological/syntactic features (may be None)

    morph_api.realize_verb(lemma: str, features: dict) -> str
        - lemma: the "have"-verb lemma from language profile.
        - features: includes tense, polarity, agreement, etc.

    morph_api.join_tokens(tokens: list[str]) -> str
        - Combines surface tokens into a final string (handles spacing,
          cliticization, script-specific behavior).

This construction never assumes spaces between tokens; it always delegates
token joining to `morph_api.join_tokens`.
"""

from typing import Any, Dict


def realize(
    slots: Dict[str, Any],
    lang_profile: Dict[str, Any],
    morph_api: Any,
) -> str:
    """
    Realize a possessive clause with a "have"-type verb.

    Args:
        slots:
            Dictionary of semantic slots, as described in the module docs.
        lang_profile:
            Language profile containing possession-have settings.
        morph_api:
            Morphological / surface-realization API (see module docs).

    Returns:
        A surface string for the possessive clause, or an empty string if
        required information is missing.
    """
    possessor_sem = slots.get("possessor")
    possessed_sem = slots.get("possessed")

    # If either side is missing, we cannot build a proper "X has Y".
    if not possessor_sem or not isinstance(possessor_sem, dict):
        return ""
    if not possessed_sem or not isinstance(possessed_sem, dict):
        return ""

    tense = slots.get("tense", "pres")
    polarity = slots.get("polarity", "pos")

    # --- Language-specific settings ---

    possessive_cfg: Dict[str, Any] = lang_profile.get("possession_have", {}) or {}

    pattern: str = possessive_cfg.get("pattern", "subj_verb_obj")
    verb_lemma: str = possessive_cfg.get("verb_lemma", "have")

    # --- Realize NPs and verb ---

    possessor_np = morph_api.realize_np(
        sem=possessor_sem,
        role="possessor",
        features=possessor_sem.get("features", {}),
    )

    possessed_np = morph_api.realize_np(
        sem=possessed_sem,
        role="possessed",
        features=possessed_sem.get("features", {}),
    )

    verb_features = {
        "tense": tense,
        "polarity": polarity,
        "verb_role": "possession_have",
        # Agreement is language-specific; the morphology layer may:
        # - default to agree with possessor, or
        # - infer its own subject based on pattern.
        # We still pass possessor features as a hint.
        "subject_features": possessor_sem.get("features", {}),
    }

    verb = morph_api.realize_verb(lemma=verb_lemma, features=verb_features)

    # --- Assemble according to pattern ---

    tokens: list[str]

    if pattern == "subj_obj_verb":
        # e.g. "Marie two daughters has"
        tokens = [possessor_np, possessed_np, verb]
    elif pattern == "verb_subj_obj":
        # e.g. "Has Marie two daughters"
        tokens = [verb, possessor_np, possessed_np]
    elif pattern == "obj_verb_subj":
        # e.g. "Two daughters has Marie" (focus on possessed)
        tokens = [possessed_np, verb, possessor_np]
    else:
        # Default: "subj_verb_obj"
        # e.g. "Marie has two daughters"
        tokens = [possessor_np, verb, possessed_np]

    # Filter out empties and join via morph_api
    tokens = [t for t in tokens if t]
    if not tokens:
        return ""

    return morph_api.join_tokens(tokens)
