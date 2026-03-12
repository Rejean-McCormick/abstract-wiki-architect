# app/core/domain/constructions/copula_attributive_adj.py

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Protocol

from app.core.domain.constructions.base import SlotSignature, SlotSpec, SlotValueKind

CONSTRUCTION_ID = "copula_attributive_adj"

__all__ = [
    "CONSTRUCTION_ID",
    "SLOT_SIGNATURE",
    "MorphologyAPI",
    "AttributiveAdjSlots",
    "coerce_attributive_adj_slots",
    "realize_attributive_adj",
    "render",
    "realize",
]


SLOT_SIGNATURE = SlotSignature(
    (
        SlotSpec(
            name="subject",
            required=True,
            accepted_kinds=(SlotValueKind.ANY,),
            allow_raw_string_fallback=True,
            description="Subject NP or subject reference.",
        ),
        SlotSpec(
            name="adjective",
            required=True,
            accepted_kinds=(SlotValueKind.ANY,),
            allow_raw_string_fallback=True,
            description="Predicate adjective or adjective reference.",
        ),
        SlotSpec(
            name="tense",
            required=False,
            accepted_kinds=(SlotValueKind.ANY,),
            allow_raw_string_fallback=True,
            default_value="present",
        ),
        SlotSpec(
            name="polarity",
            required=False,
            accepted_kinds=(SlotValueKind.ANY,),
            allow_raw_string_fallback=True,
            default_value="affirmative",
        ),
        SlotSpec(
            name="degree",
            required=False,
            accepted_kinds=(SlotValueKind.ANY,),
            allow_raw_string_fallback=True,
            default_value="positive",
        ),
        SlotSpec(
            name="person",
            required=False,
            accepted_kinds=(SlotValueKind.ANY,),
            allow_raw_string_fallback=True,
            default_value=3,
        ),
        SlotSpec(
            name="subject_features",
            required=False,
            accepted_kinds=(SlotValueKind.ANY,),
            allow_raw_string_fallback=False,
            default_value={},
        ),
        SlotSpec(
            name="adjective_features",
            required=False,
            accepted_kinds=(SlotValueKind.ANY,),
            allow_raw_string_fallback=False,
            default_value={},
        ),
        SlotSpec(
            name="copula_features",
            required=False,
            accepted_kinds=(SlotValueKind.ANY,),
            allow_raw_string_fallback=False,
            default_value={},
        ),
    )
)


class MorphologyAPI(Protocol):
    """
    Minimal protocol required by this construction.
    """

    def realize_np(self, role: str, lemma: str, features: Mapping[str, Any]) -> str:
        ...

    def realize_copula(self, features: Mapping[str, Any]) -> str:
        ...

    # Optional richer hook some morphology layers may expose.
    def realize_adjective(self, lemma: str, features: Mapping[str, Any]) -> str:  # pragma: no cover - protocol hook
        ...


@dataclass(slots=True)
class AttributiveAdjSlots:
    """
    Canonical structured inputs for COPULA_ATTRIBUTIVE_ADJ.

    Canonical runtime names:
        - subject
        - adjective

    Legacy aliases preserved:
        - subject_name
        - adj_lemma
    """

    subject: str
    adjective: str

    subject_gender: str = "unknown"
    subject_number: str = "sg"
    degree: str = "positive"

    tense: str = "present"
    polarity: str = "affirmative"
    person: int = 3

    subject_features: Dict[str, Any] = field(default_factory=dict)
    adjective_features: Dict[str, Any] = field(default_factory=dict)
    copula_features: Dict[str, Any] = field(default_factory=dict)

    @property
    def subject_name(self) -> str:
        return self.subject

    @property
    def adj_lemma(self) -> str:
        return self.adjective


def _normalize_spaces(text: str) -> str:
    return " ".join(str(text or "").split())


def _mapping_or_empty(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _first_non_empty_text(*values: Any) -> Optional[str]:
    for value in values:
        if isinstance(value, str):
            cleaned = value.strip()
            if cleaned:
                return cleaned
    return None


def _stringify_scalar(value: Any, default: str) -> str:
    if value is None:
        return default
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or default
    return str(value)


def _int_or_default(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _surface_or_lemma(value: Any, *, field_name: str) -> str:
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned:
            return cleaned

    if isinstance(value, Mapping):
        candidate = _first_non_empty_text(
            value.get("surface"),
            value.get("text"),
            value.get("name"),
            value.get("label"),
            value.get("lemma"),
        )
        if candidate:
            return candidate

    raise ValueError(f"Missing required field: {field_name}")


def _extract_subject(mapping: Mapping[str, Any]) -> str:
    subject_value = mapping.get("subject")
    if subject_value is not None:
        return _surface_or_lemma(subject_value, field_name="subject")

    return _surface_or_lemma(
        mapping.get("subject_name"),
        field_name="subject",
    )


def _extract_adjective(mapping: Mapping[str, Any]) -> str:
    adjective_value = mapping.get("adjective")
    if adjective_value is None:
        adjective_value = mapping.get("predicate_adj")
    if adjective_value is None:
        adjective_value = mapping.get("adj_lemma")

    return _surface_or_lemma(adjective_value, field_name="adjective")


def coerce_attributive_adj_slots(value: AttributiveAdjSlots | Mapping[str, Any]) -> AttributiveAdjSlots:
    """
    Accept either the typed dataclass or a canonical slot-map/legacy mapping.

    Supported mapping variants:
      - canonical:
          {"subject": "Marie Curie", "adjective": "Polish"}
      - structured:
          {"subject": {"name": "Marie Curie"}, "adjective": {"lemma": "Polish"}}
      - legacy:
          {"subject_name": "Marie Curie", "adj_lemma": "Polish"}
    """
    if isinstance(value, AttributiveAdjSlots):
        return value

    if not isinstance(value, Mapping):
        raise TypeError("slots must be AttributiveAdjSlots or a mapping")

    subject_features = _mapping_or_empty(value.get("subject_features"))
    adjective_features = _mapping_or_empty(value.get("adjective_features"))
    copula_features = _mapping_or_empty(value.get("copula_features"))

    # Backward-compatible extra_* aliases.
    subject_features.update(_mapping_or_empty(value.get("extra_subject_features")))
    adjective_features.update(_mapping_or_empty(value.get("extra_adj_features")))
    copula_features.update(_mapping_or_empty(value.get("extra_copula_features")))

    # If subject/adjective are structured mappings, merge their nested features too.
    raw_subject = value.get("subject")
    if isinstance(raw_subject, Mapping):
        subject_features = {
            **_mapping_or_empty(raw_subject.get("features")),
            **subject_features,
        }

    raw_adjective = value.get("adjective")
    if raw_adjective is None:
        raw_adjective = value.get("predicate_adj")
    if isinstance(raw_adjective, Mapping):
        adjective_features = {
            **_mapping_or_empty(raw_adjective.get("features")),
            **adjective_features,
        }

    return AttributiveAdjSlots(
        subject=_extract_subject(value),
        adjective=_extract_adjective(value),
        subject_gender=_stringify_scalar(value.get("subject_gender"), "unknown"),
        subject_number=_stringify_scalar(value.get("subject_number"), "sg"),
        degree=_stringify_scalar(value.get("degree"), "positive"),
        tense=_stringify_scalar(value.get("tense"), "present"),
        polarity=_stringify_scalar(value.get("polarity"), "affirmative"),
        person=_int_or_default(value.get("person"), 3),
        subject_features=subject_features,
        adjective_features=adjective_features,
        copula_features=copula_features,
    )


def _should_use_zero_copula(
    slots: AttributiveAdjSlots,
    lang_profile: Mapping[str, Any],
) -> bool:
    if bool(lang_profile.get("enforce_zero_copula", False)):
        return True

    zero_cfg = lang_profile.get("zero_copula")
    if not isinstance(zero_cfg, Mapping):
        return False

    if not bool(zero_cfg.get("enabled", False)):
        return False

    if bool(zero_cfg.get("present_only", False)):
        return slots.tense == "present"

    return True


def _realize_predicate_adjective(
    morph_api: MorphologyAPI,
    *,
    lemma: str,
    features: Mapping[str, Any],
) -> str:
    if hasattr(morph_api, "realize_adjective"):
        try:
            return str(morph_api.realize_adjective(lemma=lemma, features=features))
        except TypeError:
            # Keep compatibility with morphology layers that only expose realize_np.
            pass

    return str(
        morph_api.realize_np(
            role="predicate_adj",
            lemma=lemma,
            features=features,
        )
    )


def realize_attributive_adj(
    slots: AttributiveAdjSlots | Mapping[str, Any],
    lang_profile: Optional[Mapping[str, Any]],
    morph_api: MorphologyAPI,
) -> str:
    """
    Realize a COPULA_ATTRIBUTIVE_ADJ clause.

    Returns a surface string without final punctuation.
    """
    normalized_slots = coerce_attributive_adj_slots(slots)
    lang_profile = lang_profile or {}

    subject_features: Dict[str, Any] = {
        "role": "subject",
        "gender": normalized_slots.subject_gender,
        "number": normalized_slots.subject_number,
        "person": normalized_slots.person,
    }
    subject_features.update(normalized_slots.subject_features)

    subject_np = morph_api.realize_np(
        role="subject",
        lemma=normalized_slots.subject,
        features=subject_features,
    )

    adjective_features: Dict[str, Any] = {
        "role": "predicate_adj",
        "gender": normalized_slots.subject_gender,
        "number": normalized_slots.subject_number,
        "degree": normalized_slots.degree,
    }
    adjective_features.update(normalized_slots.adjective_features)

    adj_pred = _realize_predicate_adjective(
        morph_api,
        lemma=normalized_slots.adjective,
        features=adjective_features,
    )

    if _should_use_zero_copula(normalized_slots, lang_profile):
        copula = ""
    else:
        copula_features: Dict[str, Any] = {
            "tense": normalized_slots.tense,
            "polarity": normalized_slots.polarity,
            "person": normalized_slots.person,
            "number": normalized_slots.subject_number,
        }
        copula_features.update(normalized_slots.copula_features)
        copula = morph_api.realize_copula(copula_features)

    template = str(
        lang_profile.get(
            "attributive_adj_template",
            "{SUBJ} {COP} {ADJ}",
        )
    )

    sentence = template.format(
        SUBJ=subject_np,
        COP=copula,
        ADJ=adj_pred,
    )

    return _normalize_spaces(sentence)


# Convenience aliases used by adjacent construction modules.
render = realize_attributive_adj
realize = realize_attributive_adj