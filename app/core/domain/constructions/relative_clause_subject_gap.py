# app/core/domain/constructions/relative_clause_subject_gap.py
"""
RELATIVE_CLAUSE_SUBJECT_GAP CONSTRUCTION
----------------------------------------

Language-family-agnostic construction for subject-gap relative clauses,
where the head noun phrase is interpreted as the SUBJECT of the verb
inside the relative clause.

Examples:
    - "the scientist who discovered polonium"
    - "the woman that won the prize"

This construction returns a single NP that includes the head and its
relative clause (a complex NP), not a full independent clause.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Protocol


__all__ = [
    "MorphologyAPI",
    "RelativeClauseSubjectGapSlots",
    "realize_relative_clause_subject_gap",
    "realize",
]


class MorphologyAPI(Protocol):
    """
    Minimal morphology interface used by this construction.

    The implementation is intentionally permissive because the repository
    currently contains more than one calling convention for NP realization.
    """

    def realize_np(self, *args: Any, **kwargs: Any) -> str:
        ...

    def realize_verb(self, lemma: str, features: Mapping[str, Any]) -> str:
        ...

    def join_tokens(self, tokens: list[str]) -> str:
        ...


@dataclass
class RelativeClauseSubjectGapSlots:
    """
    Canonical input slots for subject-gap relative clauses.

    Required:
        head:
            Semantic spec for the head NP.
        rel_verb:
            Either a verb lemma string or a mapping with at least "lemma".

    Optional:
        rel_object:
            Object semantics for a transitive relative clause.
        rel_tense / rel_polarity:
            Verbal features for the relative clause.
        head_surface / rel_object_surface:
            Direct surface overrides.
        head_role / rel_object_role:
            Roles passed into the morphology layer.
        pattern_marker_override:
            Per-call override for the relative marker.
        extra_verb_features:
            Additional verbal features for the relative clause verb.
        rel_subject_resumptive_surface:
            Direct surface override for the resumptive pronoun.
    """

    head: Dict[str, Any]
    rel_verb: str | Dict[str, Any]
    rel_object: Optional[Dict[str, Any]] = None

    rel_tense: str = "past"
    rel_polarity: str = "pos"

    head_surface: Optional[str] = None
    rel_object_surface: Optional[str] = None
    rel_subject_resumptive_surface: Optional[str] = None

    head_role: str = "head"
    rel_object_role: str = "rel_object"
    resumptive_role: str = "rel_resumptive_subj"

    pattern_marker_override: Optional[str] = None
    extra_verb_features: Dict[str, Any] = field(default_factory=dict)


def _coerce_slots(
    slots: Mapping[str, Any] | RelativeClauseSubjectGapSlots,
) -> RelativeClauseSubjectGapSlots:
    if isinstance(slots, RelativeClauseSubjectGapSlots):
        return slots

    data = dict(slots or {})
    return RelativeClauseSubjectGapSlots(
        head=data.get("head") or {},
        rel_verb=data.get("rel_verb") or data.get("rel_verb_lemma") or "",
        rel_object=data.get("rel_object"),
        rel_tense=str(data.get("rel_tense", "past")),
        rel_polarity=str(data.get("rel_polarity", "pos")),
        head_surface=data.get("head_surface"),
        rel_object_surface=data.get("rel_object_surface"),
        rel_subject_resumptive_surface=data.get("rel_subject_resumptive_surface"),
        head_role=str(data.get("head_role", "head")),
        rel_object_role=str(data.get("rel_object_role", "rel_object")),
        resumptive_role=str(data.get("resumptive_role", "rel_resumptive_subj")),
        pattern_marker_override=data.get("pattern_marker_override"),
        extra_verb_features=dict(data.get("extra_verb_features") or {}),
    )


def _get_rc_cfg(lang_profile: Mapping[str, Any]) -> Dict[str, Any]:
    cfg = dict(lang_profile.get("relative_clause_subject_gap") or {})
    return {
        "position": str(cfg.get("position", "postnominal")),
        "rel_marker": str(cfg.get("rel_marker", "") or ""),
        "uses_resumptive_pronoun": bool(cfg.get("uses_resumptive_pronoun", False)),
        "resumptive_pronoun_lemma": str(cfg.get("resumptive_pronoun_lemma", "") or ""),
        "rel_marker_before_clause": bool(cfg.get("rel_marker_before_clause", True)),
        "extra_verb_features": dict(cfg.get("verb_features") or {}),
    }


def _surface_from_sem(sem: Any) -> str:
    if isinstance(sem, str):
        return sem.strip()
    if not isinstance(sem, Mapping):
        return ""
    return str(
        sem.get("surface")
        or sem.get("lemma")
        or sem.get("name")
        or sem.get("text")
        or ""
    ).strip()


def _realize_np(
    morph_api: Any,
    sem: Any,
    *,
    role: str,
    surface_override: Optional[str] = None,
) -> str:
    if surface_override and str(surface_override).strip():
        return str(surface_override).strip()

    if not sem:
        return ""

    if isinstance(sem, str):
        return sem.strip()

    if not isinstance(sem, Mapping):
        return str(sem).strip()

    features = dict(sem.get("features") or {})
    lemma = str(sem.get("lemma") or sem.get("name") or sem.get("surface") or "").strip()

    if hasattr(morph_api, "realize_np"):
        call_variants = (
            lambda: morph_api.realize_np(sem=sem, role=role, features=features),
            lambda: morph_api.realize_np(role=role, lemma=lemma, features=features),
            lambda: morph_api.realize_np(role, lemma, features),
            lambda: morph_api.realize_np(role, sem),
            lambda: morph_api.realize_np(sem),
        )
        for call in call_variants:
            try:
                value = call()
            except TypeError:
                continue
            if value:
                return str(value).strip()

    return _surface_from_sem(sem)


def _realize_verb(
    morph_api: Any,
    *,
    lemma: str,
    features: Mapping[str, Any],
) -> str:
    if hasattr(morph_api, "realize_verb"):
        try:
            value = morph_api.realize_verb(lemma=lemma, features=features)
        except TypeError:
            try:
                value = morph_api.realize_verb(lemma, features)
            except TypeError:
                value = lemma
        return str(value).strip()

    return lemma.strip()


def _join_tokens(morph_api: Any, tokens: list[str]) -> str:
    cleaned = [str(t).strip() for t in tokens if str(t).strip()]
    if not cleaned:
        return ""

    if hasattr(morph_api, "join_tokens"):
        try:
            return str(morph_api.join_tokens(cleaned)).strip()
        except TypeError:
            pass

    if hasattr(morph_api, "normalize_whitespace"):
        return str(morph_api.normalize_whitespace(" ".join(cleaned))).strip()

    return " ".join(cleaned)


def _resolve_rel_verb(
    rel_verb: str | Dict[str, Any],
) -> tuple[str, Dict[str, Any]]:
    if isinstance(rel_verb, Mapping):
        lemma = str(rel_verb.get("lemma") or "").strip()
        features = dict(rel_verb.get("features") or {})
        return lemma, features

    return str(rel_verb).strip(), {}


def realize_relative_clause_subject_gap(
    slots: Mapping[str, Any] | RelativeClauseSubjectGapSlots,
    lang_profile: Mapping[str, Any],
    morph_api: MorphologyAPI,
) -> str:
    """
    Realize a head noun phrase modified by a subject-gap relative clause.
    """
    slot_obj = _coerce_slots(slots)
    if not slot_obj.head:
        return ""

    head_np = _realize_np(
        morph_api,
        slot_obj.head,
        role=slot_obj.head_role,
        surface_override=slot_obj.head_surface,
    )
    if not head_np:
        return ""

    verb_lemma, verb_overrides = _resolve_rel_verb(slot_obj.rel_verb)
    if not verb_lemma:
        return head_np

    cfg = _get_rc_cfg(lang_profile)

    verb_features: Dict[str, Any] = {
        "tense": slot_obj.rel_tense,
        "polarity": slot_obj.rel_polarity,
        "verb_role": "relative_main",
        "subject_features": dict(slot_obj.head.get("features") or {}),
    }
    verb_features.update(cfg["extra_verb_features"])
    verb_features.update(verb_overrides)
    verb_features.update(slot_obj.extra_verb_features)

    verb = _realize_verb(
        morph_api,
        lemma=verb_lemma,
        features=verb_features,
    )

    object_np = _realize_np(
        morph_api,
        slot_obj.rel_object,
        role=slot_obj.rel_object_role,
        surface_override=slot_obj.rel_object_surface,
    )

    resumptive_np = ""
    if cfg["uses_resumptive_pronoun"] and cfg["resumptive_pronoun_lemma"]:
        resumptive_sem = {
            "lemma": cfg["resumptive_pronoun_lemma"],
            "features": dict(slot_obj.head.get("features") or {}),
        }
        resumptive_np = _realize_np(
            morph_api,
            resumptive_sem,
            role=slot_obj.resumptive_role,
            surface_override=slot_obj.rel_subject_resumptive_surface,
        )

    rel_marker = (
        slot_obj.pattern_marker_override
        if slot_obj.pattern_marker_override is not None
        else cfg["rel_marker"]
    )

    rc_tokens: list[str] = []

    if cfg["rel_marker_before_clause"] and rel_marker:
        rc_tokens.append(rel_marker)

    if resumptive_np:
        rc_tokens.append(resumptive_np)

    if verb:
        rc_tokens.append(verb)

    if object_np:
        rc_tokens.append(object_np)

    if not cfg["rel_marker_before_clause"] and rel_marker:
        rc_tokens.append(rel_marker)

    rc_string = _join_tokens(morph_api, rc_tokens)
    if not rc_string:
        return head_np

    if cfg["position"] == "prenominal":
        return _join_tokens(morph_api, [rc_string, head_np])

    return _join_tokens(morph_api, [head_np, rc_string])


def realize(
    slots: Dict[str, Any],
    lang_profile: Dict[str, Any],
    morph_api: Any,
) -> str:
    """
    Backward-compatible entry point retained for legacy callers.
    """
    return realize_relative_clause_subject_gap(slots, lang_profile, morph_api)