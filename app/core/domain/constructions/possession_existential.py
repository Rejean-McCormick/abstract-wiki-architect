# app/core/domain/constructions/possession_existential.py

"""
POSSESSION EXISTENTIAL CONSTRUCTION
-----------------------------------

Family-agnostic construction for possession expressed via an existential
strategy, e.g.:

    "To Marie Curie there existed two daughters."
    "У Марии Кюри было двое детей."
    "マリー・キュリーには二人の娘がいた。"
    "Laha ibnatān."

Canonical semantic slots:
    - possessor
    - possessed

This module now provides:
    - a stable construction id,
    - typed slots for new planner/runtime code,
    - a backward-compatible wrapper for legacy dict callers.

Legacy compatibility remains for the older interface built around:
    slots["possessor"]
    slots["possessed"]
    slots["tense"]
    slots["polarity"]
    slots["aspect"]
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Protocol, Sequence

CONSTRUCTION_ID = "possession_existential"

CANONICAL_SLOT_NAMES = (
    "possessor",
    "possessed",
)

LEGACY_SLOT_ALIASES = {
    "possessor": "possessor",
    "possessed": "possessed",
    "tense": "tense",
    "polarity": "polarity",
    "aspect": "aspect",
}

__all__ = [
    "CONSTRUCTION_ID",
    "CANONICAL_SLOT_NAMES",
    "LEGACY_SLOT_ALIASES",
    "MorphologyAPI",
    "PossessionExistentialSlots",
    "realize_possession_existential",
    "render",
    "realize",
]


class MorphologyAPI(Protocol):
    """
    Minimal protocol for morphology backends used by this construction.
    Implementations may support stricter or looser signatures; helpers below
    are defensive about call shapes.
    """

    def realize_np(self, *args: Any, **kwargs: Any) -> str:
        ...

    def realize_verb(self, *args: Any, **kwargs: Any) -> str:
        ...

    def join_tokens(self, tokens: list[str]) -> str:
        ...

    def finalize_sentence(self, text: str) -> str:
        ...


@dataclass
class PossessionExistentialSlots:
    """
    Typed input for existential possession.

    New planner/runtime code should prefer this shape. Legacy dict payloads
    are still supported through `render(...)`.
    """

    possessor: Any
    possessed: Any

    tense: str = "present"
    polarity: str = "affirmative"
    aspect: Optional[str] = None
    mood: Optional[str] = None
    evidentiality: Optional[str] = None
    modality: Optional[str] = None

    exist_verb_lemma: Optional[str] = None

    extra_possessor_features: Dict[str, Any] = field(default_factory=dict)
    extra_possessed_features: Dict[str, Any] = field(default_factory=dict)
    extra_verb_features: Dict[str, Any] = field(default_factory=dict)


def _mapping_or_empty(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _normalize_spaces(text: str) -> str:
    return " ".join(str(text or "").split())


def _get_possession_cfg(lang_profile: Mapping[str, Any]) -> Dict[str, Any]:
    """
    Return the possession-existential configuration for a language.

    Supported keys:
        lang_profile["possession_existential"] = {
            "exist_verb_lemma": "exist",
            "possessor_role": "possessor_oblique",
            "possessed_role": "possessed",
            "role_order": ["possessor", "verb", "possessed"],
        }
    """
    cfg = _mapping_or_empty(lang_profile.get("possession_existential"))
    return {
        "exist_verb_lemma": str(cfg.get("exist_verb_lemma") or "exist"),
        "possessor_role": str(cfg.get("possessor_role") or "possessor_oblique"),
        "possessed_role": str(cfg.get("possessed_role") or "possessed"),
        "role_order": cfg.get("role_order") or ["possessor", "verb", "possessed"],
        "template": cfg.get("template"),
    }


def _coerce_slots(
    slots: Mapping[str, Any] | PossessionExistentialSlots,
) -> PossessionExistentialSlots:
    """
    Accept both the new typed slots object and the legacy dict shape.
    """
    if isinstance(slots, PossessionExistentialSlots):
        return slots

    data = dict(slots or {})

    return PossessionExistentialSlots(
        possessor=data.get("possessor"),
        possessed=data.get("possessed"),
        tense=str(data.get("tense") or "present"),
        polarity=str(data.get("polarity") or "affirmative"),
        aspect=data.get("aspect"),
        mood=data.get("mood"),
        evidentiality=data.get("evidentiality"),
        modality=data.get("modality"),
        exist_verb_lemma=data.get("exist_verb_lemma"),
        extra_possessor_features=_mapping_or_empty(data.get("possessor_features")),
        extra_possessed_features=_mapping_or_empty(data.get("possessed_features")),
        extra_verb_features=_mapping_or_empty(data.get("verb_features")),
    )


def _build_verb_features(slots: PossessionExistentialSlots) -> Dict[str, Any]:
    """
    Assemble the feature bundle passed to the existential verb realization.
    """
    features: Dict[str, Any] = {
        "tense": slots.tense or "present",
        "polarity": slots.polarity or "affirmative",
    }

    if slots.aspect is not None:
        features["aspect"] = slots.aspect
    if slots.mood is not None:
        features["mood"] = slots.mood
    if slots.evidentiality is not None:
        features["evidentiality"] = slots.evidentiality
    if slots.modality is not None:
        features["modality"] = slots.modality

    features.update(slots.extra_verb_features)
    return features


def _realize_np(
    concept: Any,
    *,
    role: str,
    morph_api: MorphologyAPI,
    lang_profile: Mapping[str, Any],
    extra_features: Mapping[str, Any],
) -> str:
    """
    Realize a nominal participant.

    Supports:
      - pre-surfaced strings,
      - concept mappings,
      - multiple morphology API signatures.
    """
    if concept is None:
        return ""

    if isinstance(concept, str):
        return concept.strip()

    concept_map = _mapping_or_empty(concept)
    if not concept_map:
        return str(concept).strip()

    if extra_features:
        merged = dict(concept_map)
        features = _mapping_or_empty(concept_map.get("features"))
        features.update(dict(extra_features))
        merged["features"] = features
        concept_map = merged

    realize_np = getattr(morph_api, "realize_np", None)
    if not callable(realize_np):
        return _normalize_spaces(
            concept_map.get("surface")
            or concept_map.get("text")
            or concept_map.get("name")
            or concept_map.get("lemma")
            or ""
        )

    attempts = (
        lambda: realize_np(role=role, concept=concept_map, lang_profile=lang_profile),
        lambda: realize_np(role=role, concept=concept_map),
        lambda: realize_np(sem=concept_map, role=role, features=concept_map.get("features")),
        lambda: realize_np(concept_map, role=role, lang_profile=lang_profile),
        lambda: realize_np(concept_map, role=role),
        lambda: realize_np(role, concept_map),
    )

    for attempt in attempts:
        try:
            return _normalize_spaces(attempt())
        except TypeError:
            continue

    return _normalize_spaces(
        concept_map.get("surface")
        or concept_map.get("text")
        or concept_map.get("name")
        or concept_map.get("lemma")
        or ""
    )


def _realize_existential_verb(
    *,
    lemma: str,
    features: Mapping[str, Any],
    morph_api: MorphologyAPI,
    lang_profile: Mapping[str, Any],
) -> str:
    realize_verb = getattr(morph_api, "realize_verb", None)
    if not callable(realize_verb):
        return lemma

    attempts = (
        lambda: realize_verb(lemma=lemma, features=features, lang_profile=lang_profile),
        lambda: realize_verb(lemma=lemma, features=features),
        lambda: realize_verb(lemma, features, lang_profile=lang_profile),
        lambda: realize_verb(lemma, features),
    )

    for attempt in attempts:
        try:
            return _normalize_spaces(attempt())
        except TypeError:
            continue

    return lemma


def _render_template(
    *,
    cfg: Mapping[str, Any],
    possessor_np: str,
    exist_verb: str,
    possessed_np: str,
) -> str:
    """
    Render using either a string template or the legacy role_order list.
    """
    template = cfg.get("template")
    if isinstance(template, str) and template.strip():
        rendered = template.format(
            possessor=possessor_np,
            verb=exist_verb,
            possessed=possessed_np,
        )
        return _normalize_spaces(rendered)

    role_order = cfg.get("role_order") or ["possessor", "verb", "possessed"]
    if isinstance(role_order, Sequence) and not isinstance(role_order, (str, bytes)):
        pieces: list[str] = []
        for token in role_order:
            if token == "possessor" and possessor_np:
                pieces.append(possessor_np)
            elif token == "verb" and exist_verb:
                pieces.append(exist_verb)
            elif token == "possessed" and possessed_np:
                pieces.append(possessed_np)
        return pieces

    return _normalize_spaces(f"{possessor_np} {exist_verb} {possessed_np}")


def _join_surface(text_or_tokens: Any, morph_api: MorphologyAPI) -> str:
    """
    Prefer the morphology layer for script-aware token joining.
    """
    if isinstance(text_or_tokens, str):
        return _normalize_spaces(text_or_tokens)

    tokens = [str(t).strip() for t in list(text_or_tokens or []) if str(t).strip()]
    if not tokens:
        return ""

    join_tokens = getattr(morph_api, "join_tokens", None)
    if callable(join_tokens):
        try:
            return _normalize_spaces(join_tokens(tokens))
        except TypeError:
            pass

    return " ".join(tokens)


def _finalize_sentence(text: str, morph_api: MorphologyAPI) -> str:
    """
    Preserve legacy fallback behavior: use morphology finalization if present,
    otherwise add a terminal period if missing.
    """
    text = _normalize_spaces(text)
    if not text:
        return text

    finalize_sentence = getattr(morph_api, "finalize_sentence", None)
    if callable(finalize_sentence):
        try:
            return finalize_sentence(text)
        except TypeError:
            pass

    if text.endswith("."):
        return text
    return text + "."


def realize_possession_existential(
    slots: PossessionExistentialSlots,
    lang_profile: Optional[Mapping[str, Any]],
    morph_api: MorphologyAPI,
) -> str:
    """
    Realize a possessive statement using an existential pattern.
    """
    if slots.possessor is None or slots.possessed is None:
        return ""

    profile = dict(lang_profile or {})
    cfg = _get_possession_cfg(profile)

    possessor_np = _realize_np(
        slots.possessor,
        role=str(cfg["possessor_role"]),
        morph_api=morph_api,
        lang_profile=profile,
        extra_features=slots.extra_possessor_features,
    )
    possessed_np = _realize_np(
        slots.possessed,
        role=str(cfg["possessed_role"]),
        morph_api=morph_api,
        lang_profile=profile,
        extra_features=slots.extra_possessed_features,
    )

    verb_lemma = slots.exist_verb_lemma or str(cfg["exist_verb_lemma"])
    verb_features = _build_verb_features(slots)
    exist_verb = _realize_existential_verb(
        lemma=verb_lemma,
        features=verb_features,
        morph_api=morph_api,
        lang_profile=profile,
    )

    assembled = _render_template(
        cfg=cfg,
        possessor_np=possessor_np,
        exist_verb=exist_verb,
        possessed_np=possessed_np,
    )
    surface = _join_surface(assembled, morph_api)
    return _finalize_sentence(surface, morph_api)


def render(
    slots: Mapping[str, Any],
    lang_profile: Mapping[str, Any],
    morph_api: MorphologyAPI,
) -> str:
    """
    Backward-compatible entrypoint for legacy dict callers.
    """
    normalized = _coerce_slots(slots)
    return realize_possession_existential(
        normalized,
        lang_profile=lang_profile,
        morph_api=morph_api,
    )


def realize(
    slots: Mapping[str, Any],
    lang_profile: Mapping[str, Any],
    morph_api: MorphologyAPI,
) -> str:
    """
    Generic convenience alias used by some construction callers.
    """
    return render(slots, lang_profile, morph_api)