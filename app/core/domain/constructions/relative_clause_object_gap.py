# constructions\relative_clause_object_gap.py
"""
RELATIVE_CLAUSE_OBJECT_GAP CONSTRUCTION
--------------------------------------

Family-agnostic construction for object-gap relative clauses, e.g.:

    "the element that she discovered"
    "l'élément qu'elle a découvert"
    "彼女が発見した元素"

Abstract pattern:

    HEAD_NP  +  RELATIVE_CLAUSE(HEAD = object gap)

Where the HEAD noun phrase is interpreted as the missing object inside
the relative clause.

This module does *not* handle morphology directly. Instead, it delegates
to a language-specific morphology API and uses a language profile to
determine:

- whether the relative clause is pre-/post-nominal,
- which roles to pass to the morphology layer,
- and what kind of relative marker (particle / pronoun / none) to use.

Expected external interfaces
============================

1) `lang_profile` (dict-like):

    lang_profile["relative_clause_object_gap"] = {
        "position": "postnominal",            # or "prenominal"

        "head_role": "rc_head",               # NP role for head
        "rel_subject_role": "rc_subject",     # NP role for subject inside RC

        "relative_marker_type": "particle",   # "particle" | "pronoun" | "none"
        "relative_particle": "that",          # used if type == "particle"
        "relative_pronoun_role": "rel_pronoun_obj",  # used if type == "pronoun"

        # internal order of constituents inside the RC
        "internal_word_order": ["subject", "verb"],  # "subject", "verb", "gap"
    }

Any of the keys can be omitted; reasonable defaults are used.

2) `morph_api` (object):

Must implement at least:

    morph_api.realize_np(role: str, concept: dict) -> str
    morph_api.realize_verb(lemma: str, features: dict) -> str

Optionally:

    morph_api.normalize_whitespace(text: str) -> str

If `normalize_whitespace` is not present, the raw space-joined string is returned.

3) `slots` (dict):

Expected structure (conventional keys, but extensible):

    slots = {
        "head": {...},               # concept dict for head NP
        "rel_subject": {...},        # concept dict for RC subject (optional)
        "rel_verb_lemma": "discover",

        "rel_tense": "past",         # optional, default "past"
        "rel_polarity": "affirmative",
        "rel_aspect": "perfective",

        # Optional extra features:
        "rel_mood": ...,
        "rel_evidentiality": ...,
        ...
    }

The exact internal structure of `head` and `rel_subject` is up to the
calling code and morphology layer; this construction just forwards them.
"""

from __future__ import annotations

from typing import Any, Dict, List


def _get_rc_obj_gap_cfg(lang_profile: Dict[str, Any]) -> Dict[str, Any]:
    """Return configuration for object-gap relative clauses."""
    cfg = lang_profile.get("relative_clause_object_gap", {}) or {}
    if not isinstance(cfg, dict):
        cfg = {}

    return {
        # pre- vs post-nominal RC
        "position": cfg.get("position", "postnominal"),  # or "prenominal"
        # roles for morphology
        "head_role": cfg.get("head_role", "rc_head"),
        "rel_subject_role": cfg.get("rel_subject_role", "rc_subject"),
        # relative marker strategy
        "relative_marker_type": cfg.get("relative_marker_type", "particle"),
        "relative_particle": cfg.get("relative_particle", "that"),
        "relative_pronoun_role": cfg.get("relative_pronoun_role", "rel_pronoun_obj"),
        # internal order inside the relative clause
        "internal_word_order": cfg.get(
            "internal_word_order",
            ["subject", "verb"],  # S V (object gap)
        ),
    }


def _build_rel_verb_features(slots: Dict[str, Any]) -> Dict[str, Any]:
    """
    Assemble a feature bundle for the relative-clauses' verb.

    Uses separate 'rel_*' feature keys so they do not clash with main
    clause features (if present).
    """
    features: Dict[str, Any] = {}

    # Basic features with defaults
    features["tense"] = slots.get("rel_tense", "past")
    features["polarity"] = slots.get("rel_polarity", "affirmative")
    if "rel_aspect" in slots:
        features["aspect"] = slots["rel_aspect"]

    # Copy additional features if present
    for key in ("rel_mood", "rel_evidentiality", "rel_modality"):
        if key in slots:
            # Strip 'rel_' prefix in feature name for morphology layer
            base_name = key[len("rel_") :]  # e.g. "mood"
            features[base_name] = slots[key]

    return features


def _realize_relative_marker(
    cfg: Dict[str, Any],
    slots: Dict[str, Any],
    morph_api: Any,
) -> str:
    """
    Realize the relative marker (if any), based on strategy:

        - "particle": a fixed string like "that", "que", "yang".
        - "pronoun": realized via morph_api using head's features.
        - "none": no explicit marker.
    """
    marker_type = cfg["relative_marker_type"]

    if marker_type == "none":
        return ""

    if marker_type == "particle":
        particle = cfg.get("relative_particle") or ""
        return particle

    if marker_type == "pronoun":
        # Use the HEAD concept to drive agreement of pronoun if needed.
        head_concept = slots.get("head", {})
        role = cfg.get("relative_pronoun_role", "rel_pronoun_obj")
        return morph_api.realize_np(role, head_concept)

    # Fallback: no marker
    return ""


def realize_relative_clause_object_gap(
    slots: Dict[str, Any],
    lang_profile: Dict[str, Any],
    morph_api: Any,
) -> str:
    """
    Realize a noun phrase with an object-gap relative clause.

    Examples (depending on language configuration):

        "the element that she discovered"
        "that she discovered element"
        "彼女が発見した元素"

    Args:
        slots:
            A dict with at least:
                - "head": concept dict for the head NP.
                - "rel_verb_lemma": lemma of the verb inside RC.
            Optionally:
                - "rel_subject": concept dict for subject in RC.
                - "rel_tense", "rel_polarity", "rel_aspect", etc.
        lang_profile:
            Language profile with a "relative_clause_object_gap"
            configuration section.
        morph_api:
            Morphology API implementing:
                - realize_np(role: str, concept: dict) -> str
                - realize_verb(lemma: str, features: dict) -> str
              Optionally:
                - normalize_whitespace(text: str) -> str

    Returns:
        A string representing the head noun phrase with its relative
        clause attached, without final punctuation.
    """
    if not isinstance(slots, dict):
        raise TypeError("slots must be a dict")
    if "head" not in slots:
        raise ValueError("slots must contain 'head'")
    if "rel_verb_lemma" not in slots:
        raise ValueError("slots must contain 'rel_verb_lemma'")

    cfg = _get_rc_obj_gap_cfg(lang_profile)

    # Realize the head noun phrase
    head_np = morph_api.realize_np(cfg["head_role"], slots["head"])

    # Realize subject inside RC (if present)
    rel_subject_concept = slots.get("rel_subject")
    if rel_subject_concept is not None:
        rc_subject_np = morph_api.realize_np(
            cfg["rel_subject_role"], rel_subject_concept
        )
    else:
        rc_subject_np = ""

    # Realize the RC verb
    rel_verb_lemma = slots["rel_verb_lemma"]
    verb_features = _build_rel_verb_features(slots)
    rc_verb = morph_api.realize_verb(rel_verb_lemma, verb_features)

    # Relative marker (particle/pronoun/none)
    rel_marker = _realize_relative_marker(cfg, slots, morph_api)

    # Build internal RC clause (without head)
    rc_pieces: List[str] = []
    for token in cfg["internal_word_order"]:
        if token == "subject" and rc_subject_np:
            rc_pieces.append(rc_subject_np)
        elif token == "verb" and rc_verb:
            rc_pieces.append(rc_verb)
        elif token == "gap":
            # Object gap: no surface token
            continue
        # Ignore unknown tokens for forward-compatibility.

    rc_clause_core = " ".join(p for p in rc_pieces if p)

    # Prepend marker if any
    if rel_marker:
        rc_full = " ".join(p for p in [rel_marker, rc_clause_core] if p)
    else:
        rc_full = rc_clause_core

    # Now attach RC to head based on position
    position = cfg["position"]
    if position == "prenominal":
        # RC before head: [RC] [Head]
        combined = " ".join(p for p in [rc_full, head_np] if p)
    else:
        # Default: postnominal: [Head] [RC]
        combined = " ".join(p for p in [head_np, rc_full] if p)

    # Optional whitespace normalization by morphology layer
    if hasattr(morph_api, "normalize_whitespace"):
        return morph_api.normalize_whitespace(combined)

    return combined.strip()
