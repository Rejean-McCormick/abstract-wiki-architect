# app/core/domain/constructions/slot_models.py
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Optional, Sequence, Tuple, TypeAlias


# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

SlotScalar: TypeAlias = str | int | float | bool | None
FeatureMap: TypeAlias = Mapping[str, Any]
MutableFeatureMap: TypeAlias = dict[str, Any]
SlotAtom: TypeAlias = "EntityRef | LexemeRef | SlotScalar"
SlotValue: TypeAlias = "EntityRef | LexemeRef | SlotScalar | tuple[EntityRef | LexemeRef | SlotScalar, ...]"

_MISSING = object()


# ---------------------------------------------------------------------------
# Normalized slot value kinds
# ---------------------------------------------------------------------------

class SlotValueKind(str, Enum):
    """
    Coarse runtime categories for values that may appear in a slot.

    Notes:
        - ENTITY and LEXEME are the preferred normalized runtime forms.
        - LITERAL covers scalar fallback values (dates, numerals, strings, etc.).
        - SEQUENCE is only valid when a construction explicitly allows it.
        - ANY is intended for permissive transitional contracts.
        - UNKNOWN is used only by classifiers; specs should not depend on it.
    """

    ENTITY = "entity"
    LEXEME = "lexeme"
    LITERAL = "literal"
    SEQUENCE = "sequence"
    ANY = "any"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Canonical normalized slot values
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class EntityRef:
    """
    Canonical normalized entity reference used in slots.

    Aligned with the construction-runtime docs:
      - required: label
      - optional: entity_id, qid, entity_type, gender, number, person,
        surface_hint, features
    """

    label: str
    entity_id: Optional[str] = None
    qid: Optional[str] = None
    entity_type: Optional[str] = None
    gender: Optional[str] = None
    number: Optional[str] = None
    person: Optional[int | str] = None
    surface_hint: Optional[str] = None
    features: MutableFeatureMap = field(default_factory=dict)

    def __post_init__(self) -> None:
        label = _clean_required_text(self.label, field_name="label")
        object.__setattr__(self, "label", label)
        object.__setattr__(self, "entity_id", _clean_optional_text(self.entity_id))
        object.__setattr__(self, "qid", _clean_optional_text(self.qid))
        object.__setattr__(self, "entity_type", _clean_optional_text(self.entity_type))
        object.__setattr__(self, "gender", _clean_optional_text(self.gender))
        object.__setattr__(self, "number", _clean_optional_text(self.number))
        object.__setattr__(self, "surface_hint", _clean_optional_text(self.surface_hint))
        object.__setattr__(self, "features", _copy_mapping(self.features))

    @property
    def primary_id(self) -> Optional[str]:
        return self.entity_id or self.qid

    def with_feature(self, key: str, value: Any) -> "EntityRef":
        data = self.to_dict()
        features = dict(self.features)
        features[key] = value
        data["features"] = features
        return EntityRef.from_mapping(data)

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "entity_id": self.entity_id,
            "qid": self.qid,
            "entity_type": self.entity_type,
            "gender": self.gender,
            "number": self.number,
            "person": self.person,
            "surface_hint": self.surface_hint,
            "features": deepcopy(self.features),
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "EntityRef":
        if not isinstance(value, Mapping):
            raise TypeError("EntityRef.from_mapping expects a mapping.")

        label = value.get("label")
        if label is None:
            label = value.get("name")
        if not isinstance(label, str) or not label.strip():
            raise ValueError("EntityRef requires a non-empty 'label' (or compatible 'name').")

        return cls(
            label=label,
            entity_id=_first_text(value, "entity_id", "id"),
            qid=_first_text(value, "qid"),
            entity_type=_first_text(value, "entity_type", "type"),
            gender=_first_text(value, "gender"),
            number=_first_text(value, "number"),
            person=value.get("person"),
            surface_hint=_first_text(value, "surface_hint", "surface"),
            features=_mapping_or_empty(value.get("features")),
        )


@dataclass(frozen=True, slots=True)
class LexemeRef:
    """
    Canonical normalized lexical reference used in slots.

    Aligned with the construction-runtime docs:
      - required: lemma
      - optional: lexeme_id, qid, pos, surface_hint, source, confidence, features
    """

    lemma: str
    lexeme_id: Optional[str] = None
    qid: Optional[str] = None
    pos: Optional[str] = None
    surface_hint: Optional[str] = None
    source: str = "raw"
    confidence: float = 0.0
    features: MutableFeatureMap = field(default_factory=dict)

    def __post_init__(self) -> None:
        lemma = _clean_required_text(self.lemma, field_name="lemma")
        object.__setattr__(self, "lemma", lemma)
        object.__setattr__(self, "lexeme_id", _clean_optional_text(self.lexeme_id))
        object.__setattr__(self, "qid", _clean_optional_text(self.qid))
        object.__setattr__(self, "pos", _clean_optional_text(self.pos))
        object.__setattr__(self, "surface_hint", _clean_optional_text(self.surface_hint))
        object.__setattr__(self, "source", _clean_required_text(self.source, field_name="source"))
        object.__setattr__(self, "confidence", _validate_confidence(self.confidence))
        object.__setattr__(self, "features", _copy_mapping(self.features))

    @property
    def primary_id(self) -> Optional[str]:
        return self.lexeme_id or self.qid

    def with_feature(self, key: str, value: Any) -> "LexemeRef":
        data = self.to_dict()
        features = dict(self.features)
        features[key] = value
        data["features"] = features
        return LexemeRef.from_mapping(data)

    def to_dict(self) -> dict[str, Any]:
        return {
            "lemma": self.lemma,
            "lexeme_id": self.lexeme_id,
            "qid": self.qid,
            "pos": self.pos,
            "surface_hint": self.surface_hint,
            "source": self.source,
            "confidence": self.confidence,
            "features": deepcopy(self.features),
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "LexemeRef":
        if not isinstance(value, Mapping):
            raise TypeError("LexemeRef.from_mapping expects a mapping.")

        lemma = value.get("lemma")
        if lemma is None:
            lemma = value.get("surface")
        if not isinstance(lemma, str) or not lemma.strip():
            raise ValueError("LexemeRef requires a non-empty 'lemma' (or compatible 'surface').")

        raw_conf = value.get("confidence", 0.0)
        if raw_conf is None:
            raw_conf = 0.0

        return cls(
            lemma=lemma,
            lexeme_id=_first_text(value, "lexeme_id", "id"),
            qid=_first_text(value, "qid"),
            pos=_first_text(value, "pos"),
            surface_hint=_first_text(value, "surface_hint", "surface"),
            source=_first_text(value, "source") or "raw",
            confidence=float(raw_conf),
            features=_mapping_or_empty(value.get("features")),
        )


# ---------------------------------------------------------------------------
# Slot specification models for construction contracts
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class SlotSpec:
    """
    Declaration for a single construction slot.

    This is meant to be published by construction modules and consumed by
    registries/validators. It captures:
      - whether the slot is required,
      - the accepted normalized value categories,
      - whether a sequence is allowed,
      - optional feature and POS expectations,
      - defaulting behavior,
      - whether raw-string fallback is permitted.

    Examples:
        SlotSpec(
            name="subject",
            required=True,
            accepted_kinds=(SlotValueKind.ENTITY,),
            allow_raw_string_fallback=True,
        )

        SlotSpec(
            name="profession",
            required=False,
            accepted_kinds=(SlotValueKind.LEXEME,),
            accepted_pos=("NOUN",),
            allow_raw_string_fallback=True,
        )

        SlotSpec(
            name="events",
            required=False,
            accepted_kinds=(SlotValueKind.LEXEME,),
            allow_sequence=True,
            min_items=1,
        )
    """

    name: str
    required: bool = True
    accepted_kinds: Tuple[SlotValueKind, ...] = (SlotValueKind.ANY,)
    allow_sequence: bool = False
    min_items: int = 0
    max_items: Optional[int] = None

    allow_raw_string_fallback: bool = False
    accepted_pos: Tuple[str, ...] = ()
    required_feature_keys: Tuple[str, ...] = ()
    recommended_feature_keys: Tuple[str, ...] = ()

    description: Optional[str] = None
    notes: Tuple[str, ...] = ()

    default_value: Any = field(default=_MISSING, repr=False, compare=False)

    def __post_init__(self) -> None:
        name = _clean_required_text(self.name, field_name="name")
        object.__setattr__(self, "name", name)

        if not self.accepted_kinds:
            raise ValueError(f"SlotSpec '{name}' must declare at least one accepted kind.")

        accepted = _dedupe_kinds(self.accepted_kinds)
        object.__setattr__(self, "accepted_kinds", accepted)

        object.__setattr__(self, "accepted_pos", _dedupe_text_items(self.accepted_pos))
        object.__setattr__(self, "required_feature_keys", _dedupe_text_items(self.required_feature_keys))
        object.__setattr__(self, "recommended_feature_keys", _dedupe_text_items(self.recommended_feature_keys))
        object.__setattr__(self, "notes", _dedupe_text_items(self.notes))
        object.__setattr__(self, "description", _clean_optional_text(self.description))

        if self.min_items < 0:
            raise ValueError(f"SlotSpec '{name}' min_items cannot be negative.")
        if self.max_items is not None and self.max_items < self.min_items:
            raise ValueError(f"SlotSpec '{name}' max_items cannot be smaller than min_items.")
        if not self.allow_sequence and (self.min_items or self.max_items is not None):
            raise ValueError(
                f"SlotSpec '{name}' declares sequence length constraints but allow_sequence=False."
            )

    @property
    def has_default(self) -> bool:
        return self.default_value is not _MISSING

    def get_default(self) -> Any:
        if self.default_value is _MISSING:
            raise KeyError(f"Slot '{self.name}' has no default.")
        return deepcopy(self.default_value)

    def allows_kind(self, kind: SlotValueKind) -> bool:
        if SlotValueKind.ANY in self.accepted_kinds:
            return kind in {
                SlotValueKind.ENTITY,
                SlotValueKind.LEXEME,
                SlotValueKind.LITERAL,
                SlotValueKind.SEQUENCE,
            }
        return kind in self.accepted_kinds

    def allows(self, value: Any) -> bool:
        try:
            self.validate_value(value)
            return True
        except (TypeError, ValueError):
            return False

    def normalize_value(self, value: Any) -> SlotValue:
        """
        Coerce common mapping-based inputs into canonical refs and validate them
        against this slot spec.
        """
        return self.validate_value(value)

    def validate_value(self, value: Any) -> SlotValue:
        if _is_slot_sequence(value):
            if not self.allow_sequence:
                raise ValueError(f"Slot '{self.name}' does not allow sequence values.")
            normalized_items = tuple(self._validate_single_value(v) for v in value)
            self._validate_sequence_size(normalized_items)
            return normalized_items

        return self._validate_single_value(value)

    def _validate_sequence_size(self, values: Sequence[SlotAtom]) -> None:
        count = len(values)
        if count < self.min_items:
            raise ValueError(
                f"Slot '{self.name}' requires at least {self.min_items} item(s); got {count}."
            )
        if self.max_items is not None and count > self.max_items:
            raise ValueError(
                f"Slot '{self.name}' allows at most {self.max_items} item(s); got {count}."
            )

    def _validate_single_value(self, value: Any) -> SlotAtom:
        normalized = coerce_slot_value(value)
        kind = classify_slot_value(normalized)

        if not self._accepts_value(normalized, kind):
            expected = ", ".join(k.value for k in self.accepted_kinds)
            raise ValueError(
                f"Slot '{self.name}' does not accept value kind '{kind.value}'. "
                f"Expected one of: {expected}."
            )

        if isinstance(normalized, LexemeRef) and self.accepted_pos:
            if normalized.pos and normalized.pos not in self.accepted_pos:
                allowed = ", ".join(self.accepted_pos)
                raise ValueError(
                    f"Slot '{self.name}' expected POS in {{{allowed}}}, got '{normalized.pos}'."
                )

        if self.required_feature_keys:
            features = extract_slot_features(normalized)
            missing = [k for k in self.required_feature_keys if k not in features]
            if missing:
                raise ValueError(
                    f"Slot '{self.name}' is missing required feature key(s): {', '.join(missing)}."
                )

        return normalized

    def _accepts_value(self, value: SlotAtom, kind: SlotValueKind) -> bool:
        if self.allows_kind(kind):
            return True

        # Controlled raw-string fallback:
        # a construction may temporarily accept a bare string even when the
        # preferred normalized shape is EntityRef or LexemeRef.
        if isinstance(value, str) and self.allow_raw_string_fallback:
            return any(
                k in self.accepted_kinds
                for k in (SlotValueKind.ENTITY, SlotValueKind.LEXEME, SlotValueKind.LITERAL)
            )

        return False


@dataclass(frozen=True, slots=True)
class SlotSignature:
    """
    Slot inventory for one construction contract.

    This model is intentionally light and registry-friendly:
      - `required` and `optional` hold the published SlotSpec objects,
      - `allow_additional_slots` controls whether unknown slot names are accepted,
      - `validate()` returns a normalized mapping with defaults applied.

    This is useful for:
      - construction registries,
      - plan validation,
      - frame-to-slots bridge checks,
      - renderer preflight validation.
    """

    required: Tuple[SlotSpec, ...] = ()
    optional: Tuple[SlotSpec, ...] = ()
    allow_additional_slots: bool = False

    def __post_init__(self) -> None:
        names: set[str] = set()
        for spec in (*self.required, *self.optional):
            if spec.name in names:
                raise ValueError(f"Duplicate slot spec name in signature: '{spec.name}'.")
            names.add(spec.name)

        req_names = {spec.name for spec in self.required}
        opt_names = {spec.name for spec in self.optional}
        overlap = req_names & opt_names
        if overlap:
            joined = ", ".join(sorted(overlap))
            raise ValueError(f"Slot(s) cannot be both required and optional: {joined}.")

    @property
    def all_specs(self) -> Tuple[SlotSpec, ...]:
        return (*self.required, *self.optional)

    @property
    def required_names(self) -> Tuple[str, ...]:
        return tuple(spec.name for spec in self.required)

    @property
    def optional_names(self) -> Tuple[str, ...]:
        return tuple(spec.name for spec in self.optional)

    @property
    def all_names(self) -> Tuple[str, ...]:
        return tuple(spec.name for spec in self.all_specs)

    def spec_for(self, slot_name: str) -> Optional[SlotSpec]:
        name = slot_name.strip()
        for spec in self.all_specs:
            if spec.name == name:
                return spec
        return None

    def has_slot(self, slot_name: str) -> bool:
        return self.spec_for(slot_name) is not None

    def validate(self, values: Mapping[str, Any] | None) -> dict[str, SlotValue]:
        """
        Validate a provided slot mapping against the signature and return a
        normalized mapping with defaults applied.
        """
        incoming = dict(values or {})
        normalized: dict[str, SlotValue] = {}

        missing = [spec.name for spec in self.required if spec.name not in incoming and not spec.has_default]
        if missing:
            raise ValueError(f"Missing required slot(s): {', '.join(sorted(missing))}.")

        known_names = set(self.all_names)
        if not self.allow_additional_slots:
            unexpected = sorted(k for k in incoming if k not in known_names)
            if unexpected:
                raise ValueError(f"Unexpected slot(s): {', '.join(unexpected)}.")

        for spec in self.all_specs:
            if spec.name in incoming:
                normalized[spec.name] = spec.normalize_value(incoming[spec.name])
            elif spec.has_default:
                normalized[spec.name] = coerce_slot_value(spec.get_default())

        if self.allow_additional_slots:
            for key, value in incoming.items():
                if key not in normalized:
                    normalized[key] = coerce_slot_value(value)

        return normalized


# ---------------------------------------------------------------------------
# Slot value helpers
# ---------------------------------------------------------------------------

def is_entity_ref_like(value: Any) -> bool:
    if isinstance(value, EntityRef):
        return True
    if isinstance(value, Mapping):
        label = value.get("label")
        name = value.get("name")
        return isinstance(label, str) and bool(label.strip()) or isinstance(name, str) and bool(name.strip())
    return False


def is_lexeme_ref_like(value: Any) -> bool:
    if isinstance(value, LexemeRef):
        return True
    if isinstance(value, Mapping):
        lemma = value.get("lemma")
        surface = value.get("surface")
        return isinstance(lemma, str) and bool(lemma.strip()) or isinstance(surface, str) and bool(surface.strip())
    return False


def is_slot_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def classify_slot_value(value: Any) -> SlotValueKind:
    if isinstance(value, EntityRef):
        return SlotValueKind.ENTITY
    if isinstance(value, LexemeRef):
        return SlotValueKind.LEXEME
    if _is_slot_sequence(value):
        return SlotValueKind.SEQUENCE
    if is_slot_scalar(value):
        return SlotValueKind.LITERAL
    if is_entity_ref_like(value):
        return SlotValueKind.ENTITY
    if is_lexeme_ref_like(value):
        return SlotValueKind.LEXEME
    return SlotValueKind.UNKNOWN


def coerce_slot_value(value: Any) -> SlotValue:
    """
    Normalize common slot values into canonical runtime objects.

    Supported coercions:
      - EntityRef -> EntityRef
      - LexemeRef -> LexemeRef
      - mapping with label/name -> EntityRef
      - mapping with lemma/surface -> LexemeRef
      - scalar literals -> preserved as-is
      - sequences -> tuple[...] with each item coerced recursively
    """
    if isinstance(value, EntityRef | LexemeRef):
        return value

    if is_entity_ref_like(value):
        return EntityRef.from_mapping(value)  # type: ignore[arg-type]

    if is_lexeme_ref_like(value):
        return LexemeRef.from_mapping(value)  # type: ignore[arg-type]

    if _is_slot_sequence(value):
        return tuple(coerce_slot_value(item) for item in value)

    if is_slot_scalar(value):
        return value

    raise TypeError(
        "Unsupported slot value. Expected EntityRef, LexemeRef, scalar literal, "
        "or a compatible mapping/sequence."
    )


def extract_slot_features(value: Any) -> dict[str, Any]:
    if isinstance(value, EntityRef | LexemeRef):
        return dict(value.features)
    if isinstance(value, Mapping):
        raw = value.get("features")
        if isinstance(raw, Mapping):
            return dict(raw)
    return {}


def slot_value_to_dict(value: Any) -> Any:
    """
    Convert a slot value into a JSON/debug-friendly structure.
    """
    if isinstance(value, EntityRef | LexemeRef):
        return value.to_dict()
    if _is_slot_sequence(value):
        return [slot_value_to_dict(v) for v in value]
    if is_slot_scalar(value):
        return value
    if isinstance(value, Mapping):
        return {str(k): slot_value_to_dict(v) for k, v in value.items()}
    raise TypeError(f"Cannot serialize slot value of type {type(value).__name__!s}.")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _clean_required_text(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"'{field_name}' must be a string.")
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"'{field_name}' cannot be empty.")
    return cleaned


def _clean_optional_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        return str(value).strip() or None
    cleaned = value.strip()
    return cleaned or None


def _validate_confidence(value: Any) -> float:
    try:
        conf = float(value)
    except (TypeError, ValueError) as exc:
        raise TypeError("confidence must be numeric.") from exc

    if not 0.0 <= conf <= 1.0:
        raise ValueError("confidence must be between 0.0 and 1.0 inclusive.")
    return conf


def _copy_mapping(value: Mapping[str, Any] | None) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise TypeError("features must be a mapping.")
    return {str(k): deepcopy(v) for k, v in value.items()}


def _mapping_or_empty(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise TypeError("Expected a mapping for features.")
    return {str(k): deepcopy(v) for k, v in value.items()}


def _first_text(mapping: Mapping[str, Any], *keys: str) -> Optional[str]:
    for key in keys:
        if key in mapping:
            cleaned = _clean_optional_text(mapping.get(key))
            if cleaned is not None:
                return cleaned
    return None


def _is_slot_sequence(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray, Mapping))


def _dedupe_kinds(kinds: Sequence[SlotValueKind]) -> tuple[SlotValueKind, ...]:
    seen: list[SlotValueKind] = []
    for kind in kinds:
        if not isinstance(kind, SlotValueKind):
            raise TypeError("accepted_kinds must contain only SlotValueKind values.")
        if kind not in seen:
            seen.append(kind)
    return tuple(seen)


def _dedupe_text_items(values: Sequence[str]) -> tuple[str, ...]:
    seen: list[str] = []
    for value in values:
        cleaned = _clean_required_text(value, field_name="text item")
        if cleaned not in seen:
            seen.append(cleaned)
    return tuple(seen)


__all__ = [
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