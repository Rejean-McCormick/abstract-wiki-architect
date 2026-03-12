# app/core/domain/constructions/transitive_event.py
from __future__ import annotations

from typing import Any, Mapping, Sequence

from .base import ClauseInput, ClauseOutput, Construction
from .slot_models import SlotSignature, SlotSpec, SlotValueKind

TRANSITIVE_EVENT_ID = "transitive_event"
LEGACY_CONSTRUCTION_ID = "TRANSITIVE_EVENT"
DEFAULT_WORD_ORDER = "SVO"

TRANSITIVE_EVENT_SIGNATURE = SlotSignature(
    required=(
        SlotSpec(
            name="subject",
            accepted_kinds=(SlotValueKind.ANY,),
            allow_raw_string_fallback=True,
            description="Agent/subject NP or surface string.",
        ),
        SlotSpec(
            name="object",
            accepted_kinds=(SlotValueKind.ANY,),
            allow_raw_string_fallback=True,
            description="Patient/object NP or surface string.",
        ),
        SlotSpec(
            name="verb_lemma",
            accepted_kinds=(SlotValueKind.LEXEME, SlotValueKind.LITERAL, SlotValueKind.ANY),
            allow_raw_string_fallback=True,
            description="Finite event verb lemma.",
        ),
    ),
    optional=(
        SlotSpec(
            name="tense",
            required=False,
            accepted_kinds=(SlotValueKind.LITERAL,),
            allow_raw_string_fallback=True,
            default_value="present",
            description="Tense feature for the verb.",
        ),
        SlotSpec(
            name="aspect",
            required=False,
            accepted_kinds=(SlotValueKind.LITERAL,),
            allow_raw_string_fallback=True,
            default_value="simple",
            description="Aspect feature for the verb.",
        ),
        SlotSpec(
            name="polarity",
            required=False,
            accepted_kinds=(SlotValueKind.LITERAL,),
            allow_raw_string_fallback=True,
            default_value="positive",
            description="Polarity feature for the verb.",
        ),
        SlotSpec(
            name="voice",
            required=False,
            accepted_kinds=(SlotValueKind.LITERAL,),
            allow_raw_string_fallback=True,
            default_value="active",
            description="Voice feature for the verb.",
        ),
        SlotSpec(
            name="verb_features",
            required=False,
            accepted_kinds=(SlotValueKind.ANY,),
            allow_raw_string_fallback=True,
            description="Additional verb feature bundle.",
        ),
    ),
    allow_additional_slots=True,
)


def _normalize_spaces(text: str) -> str:
    return " ".join((text or "").split())


def _copy_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _surface_from_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, Mapping):
        for key in ("surface", "surface_hint", "label", "name", "lemma"):
            raw = value.get(key)
            if isinstance(raw, str) and raw.strip():
                return raw.strip()
    for key in ("surface", "surface_hint", "label", "name", "lemma"):
        raw = getattr(value, key, None)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    return str(value).strip()


def _slot_features(value: Any) -> dict[str, Any]:
    features: dict[str, Any] = {}

    if isinstance(value, Mapping):
        nested = value.get("features")
        if isinstance(nested, Mapping):
            features.update(dict(nested))

        for key in (
            "gender",
            "number",
            "person",
            "case",
            "definiteness",
            "animacy",
            "proper",
        ):
            if key in value and value[key] is not None:
                features[key] = value[key]
        return features

    nested = getattr(value, "features", None)
    if isinstance(nested, Mapping):
        features.update(dict(nested))

    for key in (
        "gender",
        "number",
        "person",
        "case",
        "definiteness",
        "animacy",
        "proper",
    ):
        raw = getattr(value, key, None)
        if raw is not None:
            features[key] = raw

    return features


def _join_tokens(tokens: list[str], morph_api: Any) -> str:
    cleaned = [t.strip() for t in tokens if isinstance(t, str) and t.strip()]
    if not cleaned:
        return ""

    if hasattr(morph_api, "join_tokens"):
        try:
            return _normalize_spaces(str(morph_api.join_tokens(cleaned) or ""))
        except TypeError:
            pass

    return _normalize_spaces(" ".join(cleaned))


def _call_realize_np(value: Any, role: str, morph_api: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, str):
        return value.strip()

    features = _slot_features(value)
    if role and "role" not in features:
        features["role"] = role

    if hasattr(morph_api, "realize_np"):
        try:
            return _normalize_spaces(
                str(
                    morph_api.realize_np(
                        sem=value,
                        role=role,
                        features=features,
                    )
                    or ""
                )
            )
        except TypeError:
            try:
                return _normalize_spaces(
                    str(morph_api.realize_np(value, role=role, features=features) or "")
                )
            except TypeError:
                try:
                    return _normalize_spaces(str(morph_api.realize_np(value) or ""))
                except TypeError:
                    pass

    return _surface_from_value(value)


def _resolve_verb_lemma(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, Mapping):
        raw = value.get("lemma") or value.get("surface") or value.get("name")
        if isinstance(raw, str):
            return raw.strip()
    raw = getattr(value, "lemma", None)
    if isinstance(raw, str):
        return raw.strip()
    return str(value or "").strip()


def _call_realize_verb(
    lemma: str,
    *,
    features: Mapping[str, Any],
    lang_profile: Mapping[str, Any],
    morph_api: Any,
) -> str:
    if not lemma:
        return ""

    if hasattr(morph_api, "realize_verb"):
        try:
            return _normalize_spaces(
                str(
                    morph_api.realize_verb(
                        lemma=lemma,
                        features=dict(features),
                        lang_profile=dict(lang_profile),
                    )
                    or ""
                )
            )
        except TypeError:
            try:
                return _normalize_spaces(
                    str(morph_api.realize_verb(lemma, dict(features), dict(lang_profile)) or "")
                )
            except TypeError:
                try:
                    return _normalize_spaces(
                        str(morph_api.realize_verb(lemma=lemma, features=dict(features)) or "")
                    )
                except TypeError:
                    try:
                        return _normalize_spaces(str(morph_api.realize_verb(lemma, dict(features)) or ""))
                    except TypeError:
                        pass

    return lemma.strip()


def _resolve_word_order(lang_profile: Mapping[str, Any]) -> str:
    raw = str(lang_profile.get("basic_word_order", DEFAULT_WORD_ORDER) or DEFAULT_WORD_ORDER).upper()
    if raw in {"SVO", "SOV", "VSO", "VOS", "OVS", "OSV"}:
        return raw
    return DEFAULT_WORD_ORDER


def _linearize(
    word_order: str,
    *,
    subject: str,
    verb: str,
    object_: str,
) -> list[str]:
    if word_order == "SOV":
        tokens = [subject, object_, verb]
    elif word_order == "VSO":
        tokens = [verb, subject, object_]
    elif word_order == "VOS":
        tokens = [verb, object_, subject]
    elif word_order == "OVS":
        tokens = [object_, verb, subject]
    elif word_order == "OSV":
        tokens = [object_, subject, verb]
    else:
        tokens = [subject, verb, object_]

    return [token for token in tokens if token]


def to_clause_input(slots: Mapping[str, Any]) -> ClauseInput:
    raw = dict(slots or {})
    verb_features = _copy_mapping(raw.get("verb_features"))

    defaults = {
        "tense": raw.get("tense", "present"),
        "aspect": raw.get("aspect", "simple"),
        "polarity": raw.get("polarity", "positive"),
        "voice": raw.get("voice", "active"),
    }
    for key, value in defaults.items():
        if key not in verb_features and value is not None:
            verb_features[key] = value

    return ClauseInput(
        roles={
            "SUBJ": raw.get("subject"),
            "OBJ": raw.get("object"),
            "VERB": raw.get("verb_lemma"),
        },
        features={
            "verb_features": verb_features,
        },
    )


class TransitiveEventConstruction(Construction):
    id = TRANSITIVE_EVENT_ID
    legacy_id = LEGACY_CONSTRUCTION_ID
    slot_signature = TRANSITIVE_EVENT_SIGNATURE

    def realize_clause(
        self,
        abstract: ClauseInput,
        lang_profile: Mapping[str, Any],
        morph: Any,
    ) -> ClauseOutput:
        lang_profile = dict(lang_profile or {})

        subject_value = abstract.roles.get("SUBJ")
        object_value = abstract.roles.get("OBJ")
        verb_value = abstract.roles.get("VERB")

        subject_surface = _call_realize_np(subject_value, "subject", morph)
        object_surface = _call_realize_np(object_value, "object", morph)

        verb_lemma = _resolve_verb_lemma(verb_value)
        subject_features = _slot_features(subject_value)
        verb_features = _copy_mapping(abstract.features.get("verb_features"))

        for key in ("person", "number", "gender"):
            if key not in verb_features and subject_features.get(key) is not None:
                verb_features[key] = subject_features[key]

        verb_surface = _call_realize_verb(
            verb_lemma,
            features=verb_features,
            lang_profile=lang_profile,
            morph_api=morph,
        )

        word_order = _resolve_word_order(lang_profile)
        tokens = _linearize(
            word_order,
            subject=subject_surface,
            verb=verb_surface,
            object_=object_surface,
        )
        text = _join_tokens(tokens, morph)

        return ClauseOutput(
            tokens=tokens,
            text=text,
            metadata={
                "construction_id": self.id,
                "legacy_construction_id": self.legacy_id,
                "basic_word_order": word_order,
                "subject_present": bool(subject_surface),
                "object_present": bool(object_surface),
                "verb_lemma": verb_lemma,
                "verb_features": dict(verb_features),
            },
        )

    def realize(
        self,
        slots: Mapping[str, Any],
        lang_profile: Mapping[str, Any],
        morph_api: Any,
    ) -> dict[str, Any]:
        output = self.realize_clause(to_clause_input(slots), lang_profile, morph_api)
        return {
            "construction_id": self.id,
            "tokens": list(output.tokens),
            "text": output.text,
            "metadata": dict(output.metadata),
        }


_CONSTRUCTION = TransitiveEventConstruction()


def realize(
    slots: Mapping[str, Any],
    lang_profile: Mapping[str, Any],
    morph_api: Any,
) -> dict[str, Any]:
    return _CONSTRUCTION.realize(slots, lang_profile, morph_api)


def render(
    slots: Mapping[str, Any],
    lang_profile: Mapping[str, Any],
    morph_api: Any,
) -> str:
    return _CONSTRUCTION.realize_clause(
        to_clause_input(slots),
        dict(lang_profile or {}),
        morph_api,
    ).text


__all__ = [
    "TRANSITIVE_EVENT_ID",
    "TRANSITIVE_EVENT_SIGNATURE",
    "TransitiveEventConstruction",
    "to_clause_input",
    "realize",
    "render",
]