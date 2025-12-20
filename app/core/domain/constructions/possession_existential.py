# app\core\domain\constructions\possession_existential.py
# constructions\possession_existential.py
"""
POSSESSION_EXISTENTIAL CONSTRUCTION
-----------------------------------

Family-agnostic construction for encoding possession via an existential
pattern, e.g.:

    "To Marie Curie there existed two daughters."
    "У Марии Кюри было двое детей."
    "マリー・キュリーには二人の娘がいた。"
    "Laha ibnatān."  (Arabic: 'to-her two daughters')

Abstract pattern:

    POSSESSOR (in oblique/locative/dative form) + EXIST_VERB + POSSESSED_NP

This module does *not* handle any morphology directly. Instead, it
delegates to a language-specific morphology API and uses a language
profile to determine ordering and which verb to use.

Expected external interfaces
============================

1) `lang_profile` (dict-like)

    lang_profile["possession_existential"] = {
        "exist_verb_lemma": "exist",          # or language-specific lemma key
        "possessor_role": "possessor_obl",    # role passed to morph_api
        "possessed_role": "possessed",        # role passed to morph_api
        "role_order": ["possessor", "verb", "possessed"]
    }

    All keys are optional; reasonable defaults are used if missing.

2) `morph_api` (object)

The morphology API is expected to implement at least:

    morph_api.realize_np(role: str, concept: dict) -> str
    morph_api.realize_verb(lemma: str, features: dict) -> str

Optionally, it may implement:

    morph_api.finalize_sentence(text: str) -> str

If `finalize_sentence` is not present, a plain space-joined string with
a trailing period "." will be returned.

3) `slots` (dict)

Expected structure (keys are conventional, but you can pass extra keys):

    slots = {
        "possessor": {...},     # concept dict for possessor
        "possessed": {...},     # concept dict for possessed entity
        "tense": "past",        # optional, default "present"
        "polarity": "affirmative",   # optional, default "affirmative"
        "aspect": "perfective",      # optional, passed through to morph_api
        ...
    }

The exact internal structure of the `possessor` and `possessed` concepts
is up to the calling code and the morphology layer; this construction
only forwards them unchanged.
"""

from __future__ import annotations

from typing import Any, Dict, List


def _get_possession_cfg(lang_profile: Dict[str, Any]) -> Dict[str, Any]:
    """Return the possession-existential configuration for a language."""
    cfg = lang_profile.get("possession_existential", {}) or {}
    if not isinstance(cfg, dict):
        cfg = {}

    # Default configuration
    return {
        "exist_verb_lemma": cfg.get("exist_verb_lemma", "exist"),
        "possessor_role": cfg.get("possessor_role", "possessor_oblique"),
        "possessed_role": cfg.get("possessed_role", "possessed"),
        "role_order": cfg.get(
            "role_order",
            ["possessor", "verb", "possessed"],
        ),
    }


def _build_verb_features(slots: Dict[str, Any]) -> Dict[str, Any]:
    """
    Assemble a feature bundle for the existential verb from slots.

    We keep this very permissive: any extra keys are passed through
    unchanged, but we ensure that common features like tense, polarity,
    and aspect have defaults.
    """
    features: Dict[str, Any] = {}

    # Basic features with defaults
    features["tense"] = slots.get("tense", "present")
    features["polarity"] = slots.get("polarity", "affirmative")
    if "aspect" in slots:
        features["aspect"] = slots["aspect"]

    # Copy any additional feature-like keys if provided explicitly
    for key in ("mood", "evidentiality", "modality"):
        if key in slots:
            features[key] = slots[key]

    return features


def realize_possession_existential(
    slots: Dict[str, Any],
    lang_profile: Dict[str, Any],
    morph_api: Any,
) -> str:
    """
    Realize a possessive statement using an existential pattern.

    Args:
        slots:
            A dict containing at least "possessor" and "possessed"
            concept objects. May also contain "tense", "polarity",
            "aspect", etc.
        lang_profile:
            Language profile configuration for the target language,
            including a "possession_existential" section.
        morph_api:
            Language-specific morphology object implementing:
                - realize_np(role: str, concept: dict) -> str
                - realize_verb(lemma: str, features: dict) -> str
              Optionally:
                - finalize_sentence(text: str) -> str

    Returns:
        A surface string representing an existential possessive clause.
    """
    if not isinstance(slots, dict):
        raise TypeError("slots must be a dict")
    if "possessor" not in slots or "possessed" not in slots:
        raise ValueError("slots must contain 'possessor' and 'possessed' keys")

    cfg = _get_possession_cfg(lang_profile)

    # Extract concepts
    possessor_concept = slots["possessor"]
    possessed_concept = slots["possessed"]

    # Realize noun phrases through morphology
    possessor_np = morph_api.realize_np(cfg["possessor_role"], possessor_concept)
    possessed_np = morph_api.realize_np(cfg["possessed_role"], possessed_concept)

    # Realize existential verb
    verb_features = _build_verb_features(slots)
    exist_verb = morph_api.realize_verb(cfg["exist_verb_lemma"], verb_features)

    # Assemble according to role_order
    # Allowed tokens in role_order: "possessor", "verb", "possessed"
    pieces: List[str] = []
    for token in cfg["role_order"]:
        if token == "possessor":
            pieces.append(possessor_np)
        elif token == "verb":
            pieces.append(exist_verb)
        elif token == "possessed":
            pieces.append(possessed_np)
        else:
            # Unknown token; ignore for forward-compatibility
            continue

    # Join with spaces; morphology layer can later strip or normalize.
    raw_sentence = " ".join(p for p in pieces if p)

    # Delegate sentence-final normalization if available
    if hasattr(morph_api, "finalize_sentence"):
        return morph_api.finalize_sentence(raw_sentence)

    # Fallback: simple punctuation handling
    text = raw_sentence.strip()
    if not text:
        return text
    if text.endswith("."):
        return text
    return text + "."
