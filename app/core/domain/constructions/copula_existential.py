# constructions\copula_existential.py
"""
COPULA_EXISTENTIAL CONSTRUCTION
-------------------------------

Language-family-agnostic construction for existential clauses such as:

    "There is a statue in Paris."
    "In Paris there is a statue."
    "In Paris exists a statue."

This construction is responsible for:

    - Choosing the order of EXISTENT and LOCATION.
    - Inserting an expletive/dummy subject if the language uses one
      ("there" in English, "il y a" style chunks in French – though those
      would typically be modeled with a multi-word verb in the language
      profile / morph layer).
    - Inserting a default locative preposition if required ("in", "at").

It is *not* responsible for:

    - Inflecting the existential verb (tense, person, polarity).
    - Internal morphology of NPs (plural, classifiers, gender, etc.).
    - Global word order outside this clause (coordination, subordination).

Those tasks are delegated to the morphology / language-specific layer
via the `morph_api` object.

----------------------------------------------------------------------
EXPECTED INPUTS
----------------------------------------------------------------------

Slots (first argument: `slots`)

A dictionary with at least:

    {
        "existent": {
            "lemma": str,
            "features": dict   # optional, can be empty
        },
        "location": {
            "lemma": str,
            "features": dict   # optional
        } or None,
        "tense": "pres" | "past" | "fut" | ... (optional, default "pres"),
        "polarity": "pos" | "neg"          (optional, default "pos")
    }

- "existent": the thing that exists (NP semantics).
- "location": where it exists (NP semantics).
  If omitted or None, a simple existential with no explicit location is produced.

Language profile (second argument: `lang_profile`)

A dictionary providing construction-specific parameters. Suggested keys:

    "existential": {
        "pattern": "there_existent_loc"
                    | "loc_verb_existent",
        "needs_expletive": bool,
        "dummy_expletive": str | None,
        "verb_lemma": str,                 # existential verb, e.g. "be" or "exist"
        "location_preposition": str | None # default preposition, e.g. "in"
    }

Reasonable defaults are used when some keys are missing.

Morph API (third argument: `morph_api`)

An object providing at least the following methods:

    morph_api.realize_np(sem: dict, role: str, features: dict | None) -> str
        - sem: the NP semantics (contains "lemma" and optionally more)
        - role: a label such as "existent" or "location"
        - features: morphological/syntactic features (may be None)

    morph_api.realize_verb(lemma: str, features: dict) -> str
        - lemma: the existential verb lemma from language profile.
        - features: includes tense, polarity, etc.

    morph_api.join_tokens(tokens: list[str]) -> str
        - Combines surface tokens into a final string (handles spacing,
          cliticization, script-specific behavior).

This construction never assumes spaces between tokens; it always delegates
token joining to `morph_api.join_tokens`.
"""

from typing import Any, Dict, Optional


def realize(
    slots: Dict[str, Any],
    lang_profile: Dict[str, Any],
    morph_api: Any,
) -> str:
    """
    Realize an existential clause from abstract slots.

    Args:
        slots:
            Dictionary of semantic slots, as described in the module docs.
        lang_profile:
            Language profile containing existential-construction settings.
        morph_api:
            Morphological / surface-realization API (see module docs).

    Returns:
        A surface string for the existential clause.
    """
    # --- Extract semantics ---
    existent_sem = slots.get("existent")
    location_sem = slots.get("location")

    if not existent_sem or not isinstance(existent_sem, dict):
        # Without an existent, there is nothing meaningful to say.
        return ""

    tense = slots.get("tense", "pres")
    polarity = slots.get("polarity", "pos")

    # --- Language-specific settings ---
    existential_cfg: Dict[str, Any] = lang_profile.get("existential", {}) or {}

    pattern = existential_cfg.get("pattern", "there_existent_loc")
    needs_expletive: bool = bool(existential_cfg.get("needs_expletive", False))
    dummy_expletive: Optional[str] = existential_cfg.get("dummy_expletive")
    verb_lemma: str = existential_cfg.get("verb_lemma", "exist")
    loc_prep: Optional[str] = existential_cfg.get("location_preposition")

    # --- Realize core pieces (NPs and verb) ---

    # EXISTENT NP
    existent_np = morph_api.realize_np(
        sem=existent_sem,
        role="existent",
        features=existent_sem.get("features", {}),
    )

    # LOCATION NP (optional)
    location_np = ""
    if location_sem and isinstance(location_sem, dict):
        location_np = morph_api.realize_np(
            sem=location_sem,
            role="location",
            features=location_sem.get("features", {}),
        )

    # Verb form (existential verb)
    verb_features = {
        "tense": tense,
        "polarity": polarity,
        "verb_role": "existential",
    }
    verb = morph_api.realize_verb(lemma=verb_lemma, features=verb_features)

    # Optional locative phrase: PREP + location
    loc_phrase = ""
    if location_np:
        if loc_prep:
            loc_phrase = morph_api.join_tokens([loc_prep, location_np])
        else:
            loc_phrase = location_np

    # --- Assemble according to pattern ---

    tokens: list[str] = []

    if pattern == "loc_verb_existent":
        # e.g. "In Paris exists a statue."
        if loc_phrase:
            tokens.append(loc_phrase)
        tokens.append(verb)
        tokens.append(existent_np)

    else:
        # Default: "there_existent_loc"
        # e.g. "There is a statue in Paris."
        if needs_expletive and dummy_expletive:
            tokens.append(dummy_expletive)

        tokens.append(verb)
        tokens.append(existent_np)

        if loc_phrase:
            tokens.append(loc_phrase)

    # Filter out any accidental empties and join via morph_api
    tokens = [t for t in tokens if t]
    if not tokens:
        return ""

    return morph_api.join_tokens(tokens)
