# app\core\domain\constructions\relative_clause_subject_gap.py
# constructions\relative_clause_subject_gap.py
"""
RELATIVE_CLAUSE_SUBJECT_GAP CONSTRUCTION
----------------------------------------

Language-family-agnostic construction for *subject-gap* relative clauses,
where the head noun phrase is interpreted as the SUBJECT of the verb
inside the relative clause.

Typical examples:
    - "the scientist who discovered polonium"
    - "the woman that won the prize"

This construction returns a *single NP* that includes the head and its
relative clause (i.e. a complex NP), not a full independent clause.

RESPONSIBILITIES
----------------
- Attach a relative clause whose subject position is filled by the head NP.
- Choose relative-clause position:
    - postnominal: "HEAD [REL_MARKER] VERB (OBJ)"
    - prenominal:  "[REL_MARKER] VERB (OBJ) HEAD"
- Optionally insert a resumptive pronoun in subject position inside the RC
  (for languages that do not allow a pure gap).

NOT RESPONSIBLE FOR
-------------------
- Inflecting the verb (tense, agreement, polarity).
- Internal morphology of NPs (plural, classifiers, etc.).
- Global sentence word order (matrix clause).

Those are delegated to the morphology / language-specific layer via
`morph_api`.

----------------------------------------------------------------------
EXPECTED INPUTS
----------------------------------------------------------------------

Slots (first argument: `slots`)

A dictionary with at least:

    {
        "head": {
            "lemma": str,
            "features": dict   # optional
        },
        "rel_verb": str | {"lemma": str, "features": dict},
        "rel_object": {
            "lemma": str,
            "features": dict   # optional
        } or None,
        "rel_tense": "pres" | "past" | "fut" | ... (optional, default "past"),
        "rel_polarity": "pos" | "neg"               (optional, default "pos")
    }

- "head": semantics for the head NP being modified.
- "rel_verb": lemma (or dictionary with "lemma") of the verb inside the RC.
- "rel_object": optional object NP semantics inside the RC (for transitive verbs).
- "rel_tense" / "rel_polarity": verbal features for the RC.

Language profile (second argument: `lang_profile`)

A dictionary providing relative-clause-specific parameters. Suggested shape:

    "relative_clause_subject_gap": {
        "position": "postnominal" | "prenominal",
        "rel_marker": str | None,           # e.g. "who", "that", "qui"
        "uses_resumptive_pronoun": bool,
        "resumptive_pronoun_lemma": str | None,
        "rel_marker_before_clause": bool    # if True, marker precedes entire RC
    }

Defaults:
    position                 = "postnominal"
    rel_marker               = None
    uses_resumptive_pronoun  = False
    resumptive_pronoun_lemma = None
    rel_marker_before_clause = True

Morph API (third argument: `morph_api`)

An object providing at least:

    morph_api.realize_np(sem: dict, role: str, features: dict | None) -> str
        - Used for the head, object, and (if needed) resumptive pronoun.

    morph_api.realize_verb(lemma: str, features: dict) -> str
        - Used for the verb inside the relative clause.

    morph_api.join_tokens(tokens: list[str]) -> str
        - Combines tokens into a single string (handles spacing, scripts, etc.).

This construction never assumes spaces; it delegates token joining to
`morph_api.join_tokens`.
"""

from typing import Any, Dict


def realize(
    slots: Dict[str, Any],
    lang_profile: Dict[str, Any],
    morph_api: Any,
) -> str:
    """
    Realize a head noun phrase modified by a subject-gap relative clause.

    Args:
        slots:
            Dictionary of semantic slots (see module docstring).
        lang_profile:
            Language profile with relative-clause settings.
        morph_api:
            Morphological / surface-realization API.

    Returns:
        A surface string for the complex NP (head + RC), or an empty string
        if required information is missing.
    """
    head_sem = slots.get("head")
    if not head_sem or not isinstance(head_sem, dict):
        return ""

    rel_verb_info = slots.get("rel_verb")
    if not rel_verb_info:
        return ""

    rel_object_sem = slots.get("rel_object")

    rel_tense = slots.get("rel_tense", "past")
    rel_polarity = slots.get("rel_polarity", "pos")

    # --- Language-specific configuration ---

    rc_cfg: Dict[str, Any] = lang_profile.get("relative_clause_subject_gap", {}) or {}

    position: str = rc_cfg.get("position", "postnominal")
    rel_marker: str = rc_cfg.get("rel_marker", "") or ""
    uses_resumptive: bool = bool(rc_cfg.get("uses_resumptive_pronoun", False))
    resumptive_lemma: str = rc_cfg.get("resumptive_pronoun_lemma", "") or ""
    marker_before_clause: bool = bool(rc_cfg.get("rel_marker_before_clause", True))

    # --- Realize head NP ---

    head_np = morph_api.realize_np(
        sem=head_sem,
        role="head",
        features=head_sem.get("features", {}),
    )

    # --- Resolve verb lemma & features for the RC ---

    if isinstance(rel_verb_info, dict):
        verb_lemma = rel_verb_info.get("lemma")
        verb_feature_overrides = rel_verb_info.get("features", {})
    else:
        verb_lemma = str(rel_verb_info)
        verb_feature_overrides = {}

    if not verb_lemma:
        return ""

    verb_features = {
        "tense": rel_tense,
        "polarity": rel_polarity,
        "verb_role": "relative_main",
        "subject_features": head_sem.get("features", {}),
    }
    verb_features.update(verb_feature_overrides)

    verb = morph_api.realize_verb(lemma=verb_lemma, features=verb_features)

    # --- Realize object NP (if any) ---

    object_np = ""
    if rel_object_sem and isinstance(rel_object_sem, dict):
        object_np = morph_api.realize_np(
            sem=rel_object_sem,
            role="rel_object",
            features=rel_object_sem.get("features", {}),
        )

    # --- Optional resumptive pronoun (subject position in RC) ---

    resumptive_np = ""
    if uses_resumptive and resumptive_lemma:
        resumptive_sem = {
            "lemma": resumptive_lemma,
            "features": head_sem.get("features", {}),
        }
        resumptive_np = morph_api.realize_np(
            sem=resumptive_sem,
            role="rel_resumptive_subj",
            features=resumptive_sem.get("features", {}),
        )

    # --- Build the internal relative clause token sequence ---

    rc_tokens: list[str] = []

    # 1. Marker placement
    # If marker_before_clause is True, place it at the beginning of RC.
    if marker_before_clause and rel_marker:
        rc_tokens.append(rel_marker)

    # 2. Subject position: gap vs resumptive pronoun.
    #    For a subject-gap RC, the subject slot is a gap; but some languages
    #    realize a resumptive pronoun here.
    if resumptive_np:
        rc_tokens.append(resumptive_np)

    # 3. Verb
    rc_tokens.append(verb)

    # 4. Object, if present
    if object_np:
        rc_tokens.append(object_np)

    # If marker should not precede the clause, but be attached later, we
    # interpret that as "postposed marker" (e.g. some particles). For now
    # we simply append it at the end of RC.
    if not marker_before_clause and rel_marker:
        rc_tokens.append(rel_marker)

    rc_tokens = [t for t in rc_tokens if t]

    if not rc_tokens:
        # If we somehow failed to build any relative-clause material,
        # fall back to just the head NP.
        return head_np

    rc_string = morph_api.join_tokens(rc_tokens)

    # --- Attach RC to head according to position ---

    if position == "prenominal":
        # [RC] + HEAD
        combined_tokens = [rc_string, head_np]
    else:
        # Default: postnominal → HEAD + [RC]
        combined_tokens = [head_np, rc_string]

    combined_tokens = [t for t in combined_tokens if t]
    if not combined_tokens:
        return ""

    return morph_api.join_tokens(combined_tokens)
