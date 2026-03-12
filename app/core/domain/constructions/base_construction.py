# app/core/domain/constructions/base_construction.py
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar, Mapping, Optional

from .base import (
    ClauseInput,
    ClauseOutput,
    MorphologyAPI,
    bool_feature,
    get_role,
    str_feature,
)
from .slot_models import (
    EntityRef,
    LexemeRef,
    SlotAtom,
    SlotScalar,
    SlotSpec,
    SlotSignature,
    SlotValue,
    SlotValueKind,
    classify_slot_value,
    coerce_slot_value,
    extract_slot_features,
    is_entity_ref_like,
    is_lexeme_ref_like,
    is_slot_scalar,
    slot_value_to_dict,
)

__all__ = [
    # base construction API
    "ConstructionContractError",
    "InvalidConstructionIdentifierError",
    "normalize_runtime_id",
    "normalize_slot_name",
    "normalize_lang_code",
    "ConstructionContext",
    "BaseConstruction",
    "Construction",
    # compatibility re-exports from .base
    "ClauseInput",
    "ClauseOutput",
    "MorphologyAPI",
    "get_role",
    "bool_feature",
    "str_feature",
    # normalized slot-contract re-exports from .slot_models
    "SlotScalar",
    "SlotAtom",
    "SlotValue",
    "SlotValueKind",
    "EntityRef",
    "LexemeRef",
    "SlotSpec",
    "SlotSignature",
    "is_entity_ref_like",
    "is_lexeme_ref_like",
    "is_slot_scalar",
    "classify_slot_value",
    "coerce_slot_value",
    "extract_slot_features",
    "slot_value_to_dict",
]


_RUNTIME_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_SLOT_NAME_RE = _RUNTIME_ID_RE
_LANG_CODE_RE = re.compile(r"^[a-z][a-z0-9_]*$")


class ConstructionContractError(ValueError):
    """Base error for construction-contract validation failures."""


class InvalidConstructionIdentifierError(ConstructionContractError):
    """Raised when a construction ID, slot name, or runtime lang code is invalid."""


def _clean_required_text(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string.")
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{field_name} cannot be empty.")
    return cleaned


def _copy_mapping(value: Mapping[str, Any] | None) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise TypeError(f"Expected a mapping, got {type(value).__name__}.")
    return {str(k): v for k, v in value.items()}


def normalize_runtime_id(value: Any, *, field_name: str = "construction_id") -> str:
    """
    Normalize a canonical runtime construction identifier.

    Construction runtime IDs are snake_case, e.g.:
        - copula_equative_simple
        - transitive_event
        - relative_clause_subject_gap
    """
    text = _clean_required_text(value, field_name=field_name)
    if not _RUNTIME_ID_RE.fullmatch(text):
        raise InvalidConstructionIdentifierError(
            f"{field_name} must be canonical snake_case; got {value!r}."
        )
    return text


def normalize_slot_name(value: Any, *, field_name: str = "slot_name") -> str:
    """Normalize a canonical slot name."""
    text = _clean_required_text(value, field_name=field_name)
    if not _ SLOT_NAME_RE.fullmatch(text):
        raise InvalidConstructionIdentifierError(
            f"{field_name} must be canonical snake_case; got {value!r}."
        )
    return text


def normalize_lang_code(value: Any, *, field_name: str = "lang_code") -> str:
    """Normalize a runtime language code such as en, fr, pt_br, sr_latn."""
    text = _clean_required_text(value, field_name=field_name).lower()
    if not _LANG_CODE_RE.fullmatch(text):
        raise InvalidConstructionIdentifierError(
            f"{field_name} must be lowercase runtime-safe text; got {value!r}."
        )
    return text


@dataclass(frozen=True, slots=True)
class ConstructionContext:
    """
    Lightweight runtime context for construction realization.

    This is intentionally small and backend-agnostic. It can be passed around
    by higher-level planner / renderer orchestration without leaking engine-
    specific details into the construction layer.
    """

    lang_code: Optional[str] = None
    lang_profile: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.lang_code is not None:
            object.__setattr__(
                self,
                "lang_code",
                normalize_lang_code(self.lang_code, field_name="ConstructionContext.lang_code"),
            )
        object.__setattr__(self, "lang_profile", _copy_mapping(self.lang_profile))
        object.__setattr__(self, "metadata", _copy_mapping(self.metadata))


class BaseConstruction(ABC):
    """
    Canonical base class for construction modules.

    Design goals
    ------------
    - Keep construction IDs stable and snake_case.
    - Publish slot contracts via `slot_signature`.
    - Normalize and validate incoming slot maps.
    - Bridge typed slot maps into the legacy `ClauseInput`/`ClauseOutput`
      interface still used by parts of the repository.
    - Stay backend-agnostic: no GF-specific, family-specific, or API-specific
      behavior belongs here.

    Subclasses should define:

        construction_id = "copula_equative_simple"
        slot_signature = SlotSignature(...)

    and implement:

        realize_clause(
            abstract: ClauseInput,
            lang_profile: dict[str, Any],
            morph: MorphologyAPI,
        ) -> ClauseOutput
    """

    construction_id: ClassVar[str] = "base_construction"
    slot_signature: ClassVar[SlotSignature] = SlotSignature(allow_additional_slots=False)
    description: ClassVar[Optional[str]] = None
    legacy_ids: ClassVar[tuple[str, ...]] = ()

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)

        if cls is BaseConstruction:
            return

        cls.construction_id = normalize_runtime_id(
            getattr(cls, "construction_id", cls.__name__),
            field_name=f"{cls.__name__}.construction_id",
        )

        signature = getattr(cls, "slot_signature", None)
        if not isinstance(signature, SlotSignature):
            raise TypeError(
                f"{cls.__name__}.slot_signature must be a SlotSignature instance."
            )

        raw_legacy_ids = getattr(cls, "legacy_ids", ())
        if raw_legacy_ids is None:
            raw_legacy_ids = ()
        cls.legacy_ids = tuple(
            str(raw).strip()
            for raw in raw_legacy_ids
            if isinstance(raw, str) and raw.strip()
        )

    @classmethod
    def runtime_id(cls) -> str:
        return cls.construction_id

    @classmethod
    def canonical_ids(cls) -> tuple[str, ...]:
        """
        Canonical runtime ID followed by any legacy aliases.

        The canonical ID is the only ID constructions should emit into new
        planner/runtime metadata.
        """
        return (cls.runtime_id(), *cls.legacy_ids)

    @classmethod
    def supports_id(cls, raw_id: str) -> bool:
        """
        Return True if `raw_id` matches the canonical or a legacy ID.
        """
        if not isinstance(raw_id, str):
            return False
        cleaned = raw_id.strip()
        return cleaned in cls.canonical_ids()

    @classmethod
    def signature(cls) -> SlotSignature:
        return cls.slot_signature

    @classmethod
    def required_slot_names(cls) -> tuple[str, ...]:
        return cls.slot_signature.required_names

    @classmethod
    def optional_slot_names(cls) -> tuple[str, ...]:
        return cls.slot_signature.optional_names

    @classmethod
    def all_slot_names(cls) -> tuple[str, ...]:
        return cls.slot_signature.all_names

    @classmethod
    def spec_for_slot(cls, slot_name: str) -> Optional[SlotSpec]:
        return cls.slot_signature.spec_for(normalize_slot_name(slot_name))

    @classmethod
    def has_slot(cls, slot_name: str) -> bool:
        return cls.spec_for_slot(slot_name) is not None

    @classmethod
    def normalize_slot_map(
        cls,
        slot_map: Mapping[str, Any] | None,
    ) -> dict[str, SlotValue]:
        """
        Validate and normalize a slot map according to the published signature.
        """
        try:
            return cls.slot_signature.validate(slot_map)
        except (TypeError, ValueError) as exc:
            raise ConstructionContractError(
                f"{cls.runtime_id()}: invalid slot_map: {exc}"
            ) from exc

    @classmethod
    def require_slot(
        cls,
        slot_map: Mapping[str, SlotValue],
        slot_name: str,
    ) -> SlotValue:
        key = normalize_slot_name(slot_name)
        if key not in slot_map:
            raise KeyError(f"{cls.runtime_id()} requires slot {key!r}.")
        return slot_map[key]

    @classmethod
    def optional_slot(
        cls,
        slot_map: Mapping[str, SlotValue],
        slot_name: str,
        default: Any = None,
    ) -> Any:
        key = normalize_slot_name(slot_name)
        return slot_map.get(key, default)

    @classmethod
    def slot_features(
        cls,
        slot_map: Mapping[str, SlotValue],
        slot_name: str,
    ) -> dict[str, Any]:
        value = cls.require_slot(slot_map, slot_name)
        return extract_slot_features(value)

    @classmethod
    def slot_debug_payload(
        cls,
        slot_map: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        """
        Return a stable JSON/debug-friendly view of a normalized slot map.
        """
        normalized = cls.normalize_slot_map(slot_map)
        return {
            name: {
                "kind": classify_slot_value(value).value,
                "value": slot_value_to_dict(value),
                "features": extract_slot_features(value),
            }
            for name, value in normalized.items()
        }

    @classmethod
    def slot_contract(cls) -> dict[str, Any]:
        """
        Return a serializable description of the published slot contract.
        """
        def _spec_to_dict(spec: SlotSpec) -> dict[str, Any]:
            return {
                "name": spec.name,
                "required": spec.required,
                "accepted_kinds": [kind.value for kind in spec.accepted_kinds],
                "allow_sequence": spec.allow_sequence,
                "min_items": spec.min_items,
                "max_items": spec.max_items,
                "allow_raw_string_fallback": spec.allow_raw_string_fallback,
                "accepted_pos": list(spec.accepted_pos),
                "required_feature_keys": list(spec.required_feature_keys),
                "recommended_feature_keys": list(spec.recommended_feature_keys),
                "description": spec.description,
                "notes": list(spec.notes),
                "has_default": spec.has_default,
            }

        return {
            "construction_id": cls.runtime_id(),
            "legacy_ids": list(cls.legacy_ids),
            "description": cls.description,
            "allow_additional_slots": cls.slot_signature.allow_additional_slots,
            "required": [_spec_to_dict(spec) for spec in cls.slot_signature.required],
            "optional": [_spec_to_dict(spec) for spec in cls.slot_signature.optional],
        }

    @classmethod
    def build_clause_input(
        cls,
        slot_map: Mapping[str, Any] | None,
        *,
        features: Mapping[str, Any] | None = None,
        lang_code: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> ClauseInput:
        """
        Convert a validated slot map into the legacy ClauseInput bridge shape.

        Notes
        -----
        - Roles are emitted using canonical slot names.
        - Typed refs are converted into JSON/debug-friendly dicts.
        - This preserves the existing `ClauseInput` shape while letting new
          construction code validate against `SlotSignature`.
        """
        normalized = cls.normalize_slot_map(slot_map)
        feature_map = _copy_mapping(features)

        if lang_code is not None:
            feature_map.setdefault("lang_code", normalize_lang_code(lang_code))

        if metadata:
            feature_map.setdefault("construction_metadata", _copy_mapping(metadata))

        feature_map.setdefault("construction_id", cls.runtime_id())

        return ClauseInput(
            roles={name: slot_value_to_dict(value) for name, value in normalized.items()},
            features=feature_map,
        )

    def realize_from_slots(
        self,
        slot_map: Mapping[str, Any] | None,
        *,
        lang_profile: Mapping[str, Any] | None,
        morph: MorphologyAPI,
        features: Mapping[str, Any] | None = None,
        lang_code: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> ClauseOutput:
        """
        Validate a slot map, build a ClauseInput bridge object, and delegate to
        `realize_clause`.

        This is the recommended entrypoint for new subclasses.
        """
        abstract = self.build_clause_input(
            slot_map,
            features=features,
            lang_code=lang_code,
            metadata=metadata,
        )
        result = self.realize_clause(
            abstract=abstract,
            lang_profile=_copy_mapping(lang_profile),
            morph=morph,
        )

        if not isinstance(result, ClauseOutput):
            raise TypeError(
                f"{self.runtime_id()}.realize_clause() must return ClauseOutput, "
                f"got {type(result).__name__}."
            )

        merged_metadata = dict(result.metadata)
        merged_metadata.setdefault("construction_id", self.runtime_id())
        merged_metadata.setdefault("slot_contract", self.slot_contract())
        merged_metadata.setdefault(
            "normalized_slot_map",
            self.slot_debug_payload(slot_map),
        )

        return ClauseOutput(
            tokens=list(result.tokens),
            text=result.text,
            metadata=merged_metadata,
        )

    def __call__(
        self,
        slot_map: Mapping[str, Any] | None,
        *,
        lang_profile: Mapping[str, Any] | None,
        morph: MorphologyAPI,
        features: Mapping[str, Any] | None = None,
        lang_code: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> ClauseOutput:
        return self.realize_from_slots(
            slot_map,
            lang_profile=lang_profile,
            morph=morph,
            features=features,
            lang_code=lang_code,
            metadata=metadata,
        )

    @abstractmethod
    def realize_clause(
        self,
        abstract: ClauseInput,
        lang_profile: dict[str, Any],
        morph: MorphologyAPI,
    ) -> ClauseOutput:
        """
        Realize a clause for this construction.

        Implementations should treat:
            - `abstract.roles` as canonical slot-derived role input
            - `abstract.features` as sentence/global metadata
            - `lang_profile` as language-level configuration
            - `morph` as the only morphology/surface backend dependency
        """
        raise NotImplementedError


# Backward-friendly alias for modules that prefer the shorter name.
Construction = BaseConstruction