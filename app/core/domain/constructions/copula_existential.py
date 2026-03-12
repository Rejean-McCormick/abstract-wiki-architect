# app/core/domain/constructions/copula_existential.py
"""
COPULA_EXISTENTIAL CONSTRUCTION
-------------------------------

Language-family-agnostic construction for existential clauses such as:

    "There is a statue in Paris."
    "In Paris there is a statue."
    "In Paris exists a statue."

This construction is responsible for:

    - Choosing the order of EXISTENT and LOCATION.
    - Inserting an expletive/dummy subject if the language uses one.
    - Inserting a default locative preposition if required.

It is *not* responsible for:

    - Inflecting the existential verb beyond delegating to `morph_api`.
    - Internal morphology of NPs.
    - Global word order outside this clause.

Those tasks are delegated to the morphology / language-specific layer
via the `morph_api` object.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Protocol


__all__ = [
    "MorphologyAPI",
    "ExistentialSlots",
    "realize_copula_existential",
    "realize",
]


class MorphologyAPI(Protocol):
    """
    Minimal protocol for morphology/surface APIs used by this construction.

    The repo currently has multiple construction-era calling conventions for
    NP realization, so this protocol is intentionally permissive.
    """

    def realize_np(self, *args: Any, **kwargs: Any) -> str:
        ...

    def realize_verb(self, lemma: str, features: Mapping[str, Any]) -> str:
        ...

    def join_tokens(self, tokens: list[str]) -> str:
        ...


@dataclass
class ExistentialSlots:
    """
    Canonical slots for existential clauses.

    Required:
        existent:
            Semantic spec for the thing that exists.

    Optional:
        location:
            Semantic spec for the location.
        tense:
            Existential tense hint, defaults to "pres".
        polarity:
            Existential polarity hint, defaults to "pos".
        existent_surface / location_surface:
            Optional direct surface overrides.
        existent_role / location_role:
            Role labels passed to the morphology layer.
        extra_verb_features:
            Extra features merged into the existential verb feature bundle.
        pattern_override:
            Optional per-call override for existential linearization pattern.
        location_preposition_override:
            Optional per-call override for the locative preposition.
    """

    existent: Dict[str, Any]
    location: Optional[Dict[str, Any]] = None
    tense: str = "pres"
    polarity: str = "pos"

    existent_surface: Optional[str] = None
    location_surface: Optional[str] = None

    existent_role: str = "existent"
    location_role: str = "location"

    extra_verb_features: Dict[str, Any] = field(default_factory=dict)
    pattern_override: Optional[str] = None
    location_preposition_override: Optional[str] = None


def _coerce_slots(slots: Mapping[str, Any] | ExistentialSlots) -> ExistentialSlots:
    if isinstance(slots, ExistentialSlots):
        return slots

    data = dict(slots or {})
    return ExistentialSlots(
        existent=data.get("existent") or {},
        location=data.get("location"),
        tense=str(data.get("tense", "pres")),
        polarity=str(data.get("polarity", "pos")),
        existent_surface=data.get("existent_surface"),
        location_surface=data.get("location_surface"),
        existent_role=str(data.get("existent_role", "existent")),
        location_role=str(data.get("location_role", "location")),
        extra_verb_features=dict(data.get("extra_verb_features") or {}),
        pattern_override=data.get("pattern_override"),
        location_preposition_override=data.get("location_preposition_override"),
    )


def _get_existential_cfg(lang_profile: Mapping[str, Any]) -> Dict[str, Any]:
    cfg = dict((lang_profile.get("existential") or {}))

    return {
        "pattern": str(cfg.get("pattern", "there_existent_loc")),
        "needs_expletive": bool(cfg.get("needs_expletive", False)),
        "dummy_expletive": cfg.get("dummy_expletive"),
        "verb_lemma": str(cfg.get("verb_lemma", "exist")),
        "location_preposition": cfg.get("location_preposition"),
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
            lambda: morph_api.realize_np(sem, role=role),
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

    return " ".join(cleaned)


def _build_locative_phrase(
    morph_api: Any,
    *,
    location_np: str,
    loc_prep: Optional[str],
) -> str:
    if not location_np:
        return ""
    if loc_prep:
        return _join_tokens(morph_api, [str(loc_prep), location_np])
    return location_np


def realize_copula_existential(
    slots: Mapping[str, Any] | ExistentialSlots,
    lang_profile: Mapping[str, Any],
    morph_api: MorphologyAPI,
) -> str:
    """
    Realize an existential clause from abstract slots.

    Supported patterns:
        - there_existent_loc   -> EXPL VERB EXISTENT LOC
        - loc_there_existent   -> LOC EXPL VERB EXISTENT
        - loc_verb_existent    -> LOC VERB EXISTENT

    Unknown patterns fall back to `there_existent_loc`.
    """
    slot_obj = _coerce_slots(slots)
    if not slot_obj.existent:
        return ""

    cfg = _get_existential_cfg(lang_profile)
    pattern = slot_obj.pattern_override or cfg["pattern"]

    existent_np = _realize_np(
        morph_api,
        slot_obj.existent,
        role=slot_obj.existent_role,
        surface_override=slot_obj.existent_surface,
    )
    if not existent_np:
        return ""

    location_np = _realize_np(
        morph_api,
        slot_obj.location,
        role=slot_obj.location_role,
        surface_override=slot_obj.location_surface,
    )

    verb_features: Dict[str, Any] = {
        "tense": slot_obj.tense,
        "polarity": slot_obj.polarity,
        "verb_role": "existential",
    }
    verb_features.update(cfg["extra_verb_features"])
    verb_features.update(slot_obj.extra_verb_features)

    verb = _realize_verb(
        morph_api,
        lemma=cfg["verb_lemma"],
        features=verb_features,
    )

    loc_prep = (
        slot_obj.location_preposition_override
        if slot_obj.location_preposition_override is not None
        else cfg["location_preposition"]
    )
    loc_phrase = _build_locative_phrase(
        morph_api,
        location_np=location_np,
        loc_prep=loc_prep,
    )

    expletive = ""
    if cfg["needs_expletive"] and cfg["dummy_expletive"]:
        expletive = str(cfg["dummy_expletive"]).strip()

    if pattern == "loc_there_existent":
        tokens = [loc_phrase, expletive, verb, existent_np]
    elif pattern == "loc_verb_existent":
        tokens = [loc_phrase, verb, existent_np]
    else:
        # Default: "there_existent_loc"
        tokens = [expletive, verb, existent_np, loc_phrase]

    return _join_tokens(morph_api, tokens)


def realize(
    slots: Dict[str, Any],
    lang_profile: Dict[str, Any],
    morph_api: Any,
) -> str:
    """
    Backward-compatible entry point retained for legacy callers.
    """
    return realize_copula_existential(slots, lang_profile, morph_api)