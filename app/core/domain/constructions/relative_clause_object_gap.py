# app/core/domain/constructions/relative_clause_object_gap.py

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Protocol


CONSTRUCTION_ID = "relative_clause_object_gap"


__all__ = [
    "CONSTRUCTION_ID",
    "MorphologyAPI",
    "RelativeClauseObjectGapSlots",
    "RelativeClauseObjectGapConstruction",
    "realize_relative_clause_object_gap",
    "realize",
]


class MorphologyAPI(Protocol):
    """
    Minimal morphology protocol for this construction.

    Concrete implementations may expose slightly different call signatures,
    so the construction uses tolerant adapter helpers when calling them.
    """

    def realize_np(self, *args: Any, **kwargs: Any) -> str:
        ...

    def realize_verb(self, *args: Any, **kwargs: Any) -> str:
        ...

    def normalize_whitespace(self, text: str) -> str:
        ...

    def join_tokens(self, tokens: list[str]) -> str:
        ...


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _as_mapping(value: Any, *, field_name: str) -> Dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, str):
        cleaned = value.strip()
        return {"surface": cleaned} if cleaned else {}
    raise TypeError(f"{field_name} must be a mapping or string; got {type(value).__name__}.")


def _merge_feature_maps(*maps: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for mapping in maps:
        if not isinstance(mapping, Mapping):
            continue
        for key, value in mapping.items():
            out[str(key)] = value
    return out


def _normalize_generation_options(raw: Any) -> Dict[str, Any]:
    if not isinstance(raw, Mapping):
        return {}

    allowed = {
        "tense",
        "polarity",
        "aspect",
        "mood",
        "evidentiality",
        "modality",
        "voice",
        "register",
        "style",
    }
    out: Dict[str, Any] = {}
    for key, value in raw.items():
        skey = str(key)
        if skey in allowed:
            out[skey] = value
    return out


@dataclass(slots=True)
class RelativeClauseObjectGapSlots:
    """
    Narrow, construction-shaped slot bundle.

    Canonical semantic roles for this construction:
    - head: the NP modified by the relative clause
    - rel_subject: the subject inside the relative clause
    - rel_verb_lemma: predicate lemma inside the relative clause

    Legacy `rel_*` feature keys remain accepted for compatibility.
    """

    head: Dict[str, Any]
    rel_verb_lemma: str
    rel_subject: Optional[Dict[str, Any]] = None
    generation_options: Dict[str, Any] = field(default_factory=dict)
    rel_marker_override: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, slots: Mapping[str, Any]) -> "RelativeClauseObjectGapSlots":
        if not isinstance(slots, Mapping):
            raise TypeError("slots must be a mapping")

        head_raw = slots.get("head", slots.get("head_np", slots.get("object")))
        if head_raw is None:
            raise ValueError(
                "slots must contain 'head' "
                "(compatibility aliases: 'head_np', 'object')."
            )

        rel_subject_raw = slots.get("rel_subject", slots.get("subject"))

        rel_verb_lemma = _clean_text(
            slots.get(
                "rel_verb_lemma",
                slots.get("verb_lemma", slots.get("predicate_lemma")),
            )
        )
        if not rel_verb_lemma:
            predicate = slots.get("predicate")
            if isinstance(predicate, Mapping):
                rel_verb_lemma = _clean_text(
                    predicate.get("lemma", predicate.get("verb_lemma"))
                )

        if not rel_verb_lemma:
            raise ValueError(
                "slots must contain 'rel_verb_lemma' "
                "(compatibility aliases: 'verb_lemma', 'predicate_lemma')."
            )

        legacy_rel_features = {
            "tense": slots.get("rel_tense", slots.get("tense", "past")),
            "polarity": slots.get("rel_polarity", slots.get("polarity", "affirmative")),
        }

        if "rel_aspect" in slots:
            legacy_rel_features["aspect"] = slots["rel_aspect"]
        elif "aspect" in slots:
            legacy_rel_features["aspect"] = slots["aspect"]

        for legacy_key, canonical_key in (
            ("rel_mood", "mood"),
            ("rel_evidentiality", "evidentiality"),
            ("rel_modality", "modality"),
            ("voice", "voice"),
            ("register", "register"),
            ("style", "style"),
        ):
            if legacy_key in slots:
                legacy_rel_features[canonical_key] = slots[legacy_key]

        generation_options = _merge_feature_maps(
            _normalize_generation_options(slots.get("generation_options")),
            legacy_rel_features,
        )

        rel_marker_override = _clean_text(
            slots.get("relative_marker", slots.get("rel_marker"))
        ) or None

        metadata = {}
        if isinstance(slots.get("metadata"), Mapping):
            metadata = dict(slots["metadata"])

        rel_subject = None
        if rel_subject_raw is not None:
            rel_subject = _as_mapping(rel_subject_raw, field_name="rel_subject")

        return cls(
            head=_as_mapping(head_raw, field_name="head"),
            rel_subject=rel_subject,
            rel_verb_lemma=rel_verb_lemma,
            generation_options=generation_options,
            rel_marker_override=rel_marker_override,
            metadata=metadata,
        )


def _get_cfg(lang_profile: Mapping[str, Any]) -> Dict[str, Any]:
    raw = lang_profile.get("relative_clause_object_gap")
    if not isinstance(raw, Mapping):
        raw = {}

    order = raw.get("internal_word_order", ["subject", "verb"])
    if not isinstance(order, list):
        order = ["subject", "verb"]

    position = _clean_text(raw.get("position")) or "postnominal"
    position = position.lower()
    if position not in {"postnominal", "prenominal"}:
        position = "postnominal"

    marker_type = _clean_text(raw.get("relative_marker_type")) or "particle"
    marker_type = marker_type.lower()
    if marker_type not in {"particle", "pronoun", "none"}:
        marker_type = "particle"

    return {
        "position": position,
        "head_role": _clean_text(raw.get("head_role")) or "rc_head",
        "rel_subject_role": _clean_text(raw.get("rel_subject_role")) or "rc_subject",
        "relative_marker_type": marker_type,
        "relative_particle": _clean_text(raw.get("relative_particle")) or "that",
        "relative_pronoun_role": (
            _clean_text(raw.get("relative_pronoun_role")) or "rel_pronoun_obj"
        ),
        "internal_word_order": [str(item).strip().lower() for item in order if str(item).strip()],
    }


def _call_realize_np(
    morph_api: Any,
    *,
    role: str,
    concept: Mapping[str, Any],
    lang_profile: Mapping[str, Any],
) -> str:
    features = concept.get("features", {}) if isinstance(concept, Mapping) else {}

    attempts = (
        lambda: morph_api.realize_np(role, concept),
        lambda: morph_api.realize_np(role=role, concept=concept),
        lambda: morph_api.realize_np(concept, role=role, lang_profile=lang_profile),
        lambda: morph_api.realize_np(
            sem=concept,
            role=role,
            features=features,
            lang_profile=lang_profile,
        ),
        lambda: morph_api.realize_np(role=role, sem=concept),
    )

    last_error: Optional[Exception] = None
    for call in attempts:
        try:
            value = call()
            return _clean_text(value)
        except TypeError as exc:
            last_error = exc
            continue

    if last_error is not None:
        raise last_error
    return ""


def _call_realize_verb(
    morph_api: Any,
    *,
    lemma: str,
    features: Mapping[str, Any],
    lang_profile: Mapping[str, Any],
) -> str:
    spec = {"lemma": lemma, "features": dict(features)}

    attempts = (
        lambda: morph_api.realize_verb(lemma, dict(features)),
        lambda: morph_api.realize_verb(lemma=lemma, features=dict(features)),
        lambda: morph_api.realize_verb(spec, lang_profile=lang_profile),
        lambda: morph_api.realize_verb(
            {"lemma": lemma, **dict(features)},
            lang_profile=lang_profile,
        ),
    )

    last_error: Optional[Exception] = None
    for call in attempts:
        try:
            value = call()
            return _clean_text(value)
        except TypeError as exc:
            last_error = exc
            continue

    if last_error is not None:
        raise last_error
    return ""


def _join_tokens(parts: list[str], morph_api: Any) -> str:
    cleaned = [p.strip() for p in parts if isinstance(p, str) and p.strip()]
    if not cleaned:
        return ""

    if hasattr(morph_api, "join_tokens"):
        try:
            joined = morph_api.join_tokens(cleaned)
            return _normalize_surface(joined, morph_api)
        except TypeError:
            pass

    return _normalize_surface(" ".join(cleaned), morph_api)


def _normalize_surface(text: str, morph_api: Any) -> str:
    cleaned = _clean_text(text)
    if not cleaned:
        return ""

    if hasattr(morph_api, "normalize_whitespace"):
        try:
            return _clean_text(morph_api.normalize_whitespace(cleaned))
        except TypeError:
            pass

    return " ".join(cleaned.split())


def _realize_relative_marker(
    *,
    cfg: Mapping[str, Any],
    slots: RelativeClauseObjectGapSlots,
    morph_api: Any,
    lang_profile: Mapping[str, Any],
) -> str:
    if slots.rel_marker_override:
        return slots.rel_marker_override

    marker_type = str(cfg.get("relative_marker_type", "particle")).lower()

    if marker_type == "none":
        return ""

    if marker_type == "particle":
        return _clean_text(cfg.get("relative_particle"))

    if marker_type == "pronoun":
        return _call_realize_np(
            morph_api,
            role=str(cfg.get("relative_pronoun_role", "rel_pronoun_obj")),
            concept=slots.head,
            lang_profile=lang_profile,
        )

    return ""


class RelativeClauseObjectGapConstruction:
    """
    Family-agnostic construction for object-gap relative clauses.

    Surface pattern:
        HEAD + RC(subject + verb + object gap)

    Examples:
        "the element that she discovered"
        "the book that Marie wrote"
        "彼女が発見した元素"
    """

    construction_id = CONSTRUCTION_ID

    def realize(
        self,
        slots: Mapping[str, Any] | RelativeClauseObjectGapSlots,
        lang_profile: Mapping[str, Any],
        morph_api: MorphologyAPI,
    ) -> str:
        normalized = (
            slots
            if isinstance(slots, RelativeClauseObjectGapSlots)
            else RelativeClauseObjectGapSlots.from_mapping(slots)
        )

        cfg = _get_cfg(lang_profile or {})

        head_np = _call_realize_np(
            morph_api,
            role=str(cfg["head_role"]),
            concept=normalized.head,
            lang_profile=lang_profile,
        )

        rc_subject_np = ""
        if normalized.rel_subject:
            rc_subject_np = _call_realize_np(
                morph_api,
                role=str(cfg["rel_subject_role"]),
                concept=normalized.rel_subject,
                lang_profile=lang_profile,
            )

        verb_features = dict(normalized.generation_options)
        verb_features.setdefault("tense", "past")
        verb_features.setdefault("polarity", "affirmative")
        verb_features.setdefault("construction_id", self.construction_id)
        verb_features.setdefault("relative_clause_role", "object_gap")

        rc_verb = _call_realize_verb(
            morph_api,
            lemma=normalized.rel_verb_lemma,
            features=verb_features,
            lang_profile=lang_profile,
        )

        rel_marker = _realize_relative_marker(
            cfg=cfg,
            slots=normalized,
            morph_api=morph_api,
            lang_profile=lang_profile,
        )

        rc_pieces: list[str] = []
        for token in cfg["internal_word_order"]:
            if token == "marker" and rel_marker:
                rc_pieces.append(rel_marker)
            elif token == "subject" and rc_subject_np:
                rc_pieces.append(rc_subject_np)
            elif token == "verb" and rc_verb:
                rc_pieces.append(rc_verb)
            elif token == "gap":
                continue

        if rel_marker and "marker" not in cfg["internal_word_order"]:
            rc_pieces.insert(0, rel_marker)

        rc_clause = _join_tokens(rc_pieces, morph_api)

        if str(cfg["position"]) == "prenominal":
            combined = _join_tokens([rc_clause, head_np], morph_api)
        else:
            combined = _join_tokens([head_np, rc_clause], morph_api)

        return combined


_CONSTRUCTION = RelativeClauseObjectGapConstruction()


def realize_relative_clause_object_gap(
    slots: Mapping[str, Any],
    lang_profile: Mapping[str, Any],
    morph_api: MorphologyAPI,
) -> str:
    """
    Backward-compatible functional entry point.

    Accepted compatibility inputs:
    - `head` / `head_np` / `object`
    - `rel_subject` / `subject`
    - `rel_verb_lemma` / `verb_lemma` / `predicate_lemma`
    - legacy `rel_*` realization controls
    - optional `generation_options`
    """
    return _CONSTRUCTION.realize(slots, lang_profile or {}, morph_api)


# Alias retained for consistency with other construction modules.
realize = realize_relative_clause_object_gap