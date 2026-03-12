# app/core/domain/constructions/copula_equative_classification.py

"""
COPULA EQUATIVE CLASSIFICATION CONSTRUCTION
-------------------------------------------

This module implements the COPULA_EQUATIVE_CLASSIFICATION construction, i.e.
sentences of the form:

    "X is a Y (class / type)"

Examples:
    "Python is a programming language."
    "Marie Curie is a physicist."
    "The Nile is a river in Africa."

The construction is language-family agnostic. It delegates morphology and
language-specific details to a morphology API and an optional language profile.

Batch-ready notes:
- Exposes a stable snake_case runtime ID.
- Preserves the existing dataclass + functional entrypoint.
- Adds a construction class wrapper so the module can participate in a more
  uniform construction inventory without breaking current callers.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any, Dict, Mapping, Optional, Protocol


CONSTRUCTION_ID = "copula_equative_classification"


__all__ = [
    "CONSTRUCTION_ID",
    "MorphologyAPI",
    "EquativeClassificationSlots",
    "EquativeClassificationConstruction",
    "render",
    "realize_equative_classification",
]


class MorphologyAPI(Protocol):
    """
    Minimal protocol that any morphology layer must implement in order to be
    used by this construction.

    A concrete implementation will typically wrap one of the existing family
    engines.
    """

    def realize_np(self, role: str, lemma: str, features: Mapping[str, Any]) -> str:
        """
        Realize a noun phrase.
        """
        ...

    def realize_copula(self, features: Mapping[str, Any]) -> str:
        """
        Realize the copula ("to be") if the language uses an overt copula
        in this context. Languages with zero copula can return ''.
        """
        ...


@dataclass(slots=True)
class EquativeClassificationSlots:
    """
    Input slots for the COPULA_EQUATIVE_CLASSIFICATION construction.

    Required:
        subject_name: Surface string for the subject name (already lexicalized),
                      e.g. "Python", "Marie Curie".
        class_lemma: Lemma for the taxonomic class, e.g. "programming language",
                     "physicist", "river".

    Optional metadata is forwarded as features to the morphology layer.
    """

    subject_name: str
    class_lemma: str

    subject_gender: str = "unknown"
    subject_number: str = "sg"
    class_number: str = "sg"
    class_definiteness: str = "indefinite"

    tense: str = "present"
    polarity: str = "affirmative"
    person: int = 3

    extra_subject_features: Dict[str, Any] = field(default_factory=dict)
    extra_class_features: Dict[str, Any] = field(default_factory=dict)
    extra_copula_features: Dict[str, Any] = field(default_factory=dict)


def _normalize_spaces(text: str) -> str:
    """Collapse multiple spaces and strip leading/trailing whitespace."""
    return " ".join(str(text or "").split())


def _non_empty_string(value: Any) -> str:
    return str(value or "").strip()


def _coerce_mapping(value: Any) -> Dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _call_realize_np(
    morph_api: Any,
    *,
    role: str,
    lemma: str,
    features: Mapping[str, Any],
    lang_profile: Mapping[str, Any],
) -> str:
    """
    Best-effort dispatch for morphology implementations.

    Supported shapes seen across the repo include:
    - realize_np(role=..., lemma=..., features=...)
    - realize_np(role=..., lemma=..., features=..., lang_profile=...)
    """
    realize_np = getattr(morph_api, "realize_np", None)
    if not callable(realize_np):
        return lemma

    try:
        return str(
            realize_np(
                role=role,
                lemma=lemma,
                features=features,
                lang_profile=lang_profile,
            )
        )
    except TypeError:
        return str(realize_np(role=role, lemma=lemma, features=features))


def _call_realize_copula(
    morph_api: Any,
    *,
    features: Mapping[str, Any],
    lang_profile: Mapping[str, Any],
) -> str:
    """
    Best-effort dispatch for copula realization.

    Supported shapes seen across the repo include:
    - realize_copula(features=...)
    - realize_copula(features=..., lang_profile=...)
    """
    realize_copula = getattr(morph_api, "realize_copula", None)
    if not callable(realize_copula):
        return ""

    try:
        return str(realize_copula(features=features, lang_profile=lang_profile))
    except TypeError:
        return str(realize_copula(features=features))


def _should_drop_copula(
    *,
    lang_profile: Mapping[str, Any],
    slots: EquativeClassificationSlots,
) -> bool:
    if bool(lang_profile.get("enforce_zero_copula", False)):
        return True

    zero_cfg = lang_profile.get("zero_copula", {})
    if not isinstance(zero_cfg, Mapping) or not zero_cfg.get("enabled", False):
        return False

    if zero_cfg.get("present_only", False):
        return _non_empty_string(slots.tense).lower() in {"present", "pres"}

    return True


def _coerce_slots(slots: Any) -> EquativeClassificationSlots:
    """
    Accept the native dataclass, a plain mapping, or a dataclass-like object.
    """
    if isinstance(slots, EquativeClassificationSlots):
        return slots

    if is_dataclass(slots):
        return EquativeClassificationSlots(**asdict(slots))

    if isinstance(slots, Mapping):
        data = dict(slots)

        # Compatibility with flatter slot maps used in some neighboring modules.
        subject_name = data.get("subject_name")
        if not subject_name:
            subject = data.get("subject")
            if isinstance(subject, Mapping):
                subject_name = (
                    subject.get("name")
                    or subject.get("lemma")
                    or subject.get("surface")
                )
            elif isinstance(subject, str):
                subject_name = subject

        class_lemma = data.get("class_lemma")
        if not class_lemma:
            class_spec = data.get("class") or data.get("predicate")
            if isinstance(class_spec, Mapping):
                class_lemma = (
                    class_spec.get("lemma")
                    or class_spec.get("name")
                    or class_spec.get("surface")
                )
            elif isinstance(class_spec, str):
                class_lemma = class_spec

        return EquativeClassificationSlots(
            subject_name=_non_empty_string(subject_name),
            class_lemma=_non_empty_string(class_lemma),
            subject_gender=_non_empty_string(data.get("subject_gender") or "unknown"),
            subject_number=_non_empty_string(data.get("subject_number") or "sg"),
            class_number=_non_empty_string(data.get("class_number") or "sg"),
            class_definiteness=_non_empty_string(
                data.get("class_definiteness") or "indefinite"
            ),
            tense=_non_empty_string(data.get("tense") or "present"),
            polarity=_non_empty_string(data.get("polarity") or "affirmative"),
            person=int(data.get("person", 3)),
            extra_subject_features=_coerce_mapping(data.get("extra_subject_features")),
            extra_class_features=_coerce_mapping(data.get("extra_class_features")),
            extra_copula_features=_coerce_mapping(data.get("extra_copula_features")),
        )

    raise TypeError(
        "slots must be EquativeClassificationSlots, a dataclass instance, or a mapping"
    )


class EquativeClassificationConstruction:
    """
    Batch-ready construction wrapper around the existing realization logic.
    """

    construction_id = CONSTRUCTION_ID
    required_slots = ("subject_name", "class_lemma")

    def render(
        self,
        slots: EquativeClassificationSlots | Mapping[str, Any] | Any,
        lang_profile: Optional[Mapping[str, Any]],
        morph_api: MorphologyAPI,
    ) -> str:
        slots_obj = _coerce_slots(slots)
        profile: Dict[str, Any] = dict(lang_profile or {})

        if not _non_empty_string(slots_obj.subject_name):
            raise ValueError("COPULA_EQUATIVE_CLASSIFICATION requires `subject_name`.")
        if not _non_empty_string(slots_obj.class_lemma):
            raise ValueError("COPULA_EQUATIVE_CLASSIFICATION requires `class_lemma`.")

        subject_features: Dict[str, Any] = {
            "role": "subject",
            "gender": slots_obj.subject_gender,
            "number": slots_obj.subject_number,
            "person": slots_obj.person,
        }
        subject_features.update(slots_obj.extra_subject_features)

        class_features: Dict[str, Any] = {
            "role": "class",
            "number": slots_obj.class_number,
            "definiteness": slots_obj.class_definiteness,
            # Often useful for profession/class predicates in languages with
            # agreement-sensitive nominal predicates.
            "gender": slots_obj.subject_gender,
        }
        class_features.update(slots_obj.extra_class_features)

        subject_np = _call_realize_np(
            morph_api,
            role="subject",
            lemma=slots_obj.subject_name,
            features=subject_features,
            lang_profile=profile,
        )

        class_np = _call_realize_np(
            morph_api,
            role="class",
            lemma=slots_obj.class_lemma,
            features=class_features,
            lang_profile=profile,
        )

        copula = ""
        if not _should_drop_copula(lang_profile=profile, slots=slots_obj):
            copula_features: Dict[str, Any] = {
                "tense": slots_obj.tense,
                "polarity": slots_obj.polarity,
                "person": slots_obj.person,
                "number": slots_obj.subject_number,
            }
            copula_features.update(slots_obj.extra_copula_features)
            copula = _call_realize_copula(
                morph_api,
                features=copula_features,
                lang_profile=profile,
            )

        template = str(
            profile.get("classification_template", "{SUBJ} {COP} {CLASS}")
        ).strip() or "{SUBJ} {COP} {CLASS}"

        sentence = template.format(
            SUBJ=subject_np,
            COP=copula,
            CLASS=class_np,
        )

        return _normalize_spaces(sentence)

    def realize(
        self,
        slots: EquativeClassificationSlots | Mapping[str, Any] | Any,
        lang_profile: Optional[Mapping[str, Any]],
        morph_api: MorphologyAPI,
    ) -> str:
        return self.render(slots, lang_profile, morph_api)


def render(
    slots: EquativeClassificationSlots | Mapping[str, Any] | Any,
    lang_profile: Optional[Mapping[str, Any]],
    morph_api: MorphologyAPI,
) -> str:
    """
    Batch-friendly plain entrypoint matching the naming style used in sibling
    construction modules.
    """
    return EquativeClassificationConstruction().render(slots, lang_profile, morph_api)


def realize_equative_classification(
    slots: EquativeClassificationSlots | Mapping[str, Any] | Any,
    lang_profile: Optional[Mapping[str, Any]],
    morph_api: MorphologyAPI,
) -> str:
    """
    Backward-compatible functional entrypoint preserved for existing callers.
    """
    return render(slots, lang_profile, morph_api)