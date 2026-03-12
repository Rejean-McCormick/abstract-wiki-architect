# app/core/domain/specs/common.py
"""
Shared, backend-agnostic spec primitives for the construction runtime.

This module intentionally stays generic. It does not know about any one
construction family, renderer, or frame type. Instead, it provides the
small, stable building blocks that the construction registry and slot-model
layer can reuse to define and validate runtime contracts.

Core design goals
-----------------
1. Keep construction/slot rules out of SlotMap itself.
2. Keep runtime identifiers canonical and stable.
3. Make validation deterministic and easy to test.
4. Prefer immutable-ish dataclasses and explicit normalization helpers.
5. Stay JSON-friendly: all validated slot-map outputs remain serializable.

Typical usage
-------------
    subject = SlotSpec(
        name="subject",
        accepted_kinds=(SlotValueKind.ENTITY, SlotValueKind.STRING),
        cardinality=Cardinality.EXACTLY_ONE,
        fallback_policy=FallbackPolicy.ALLOW_RAW_STRING,
        expected_feature_keys={"number", "gender", "person"},
    )

    profession = SlotSpec(
        name="profession",
        accepted_kinds=(SlotValueKind.LEXEME, SlotValueKind.STRING),
        cardinality=Cardinality.ZERO_OR_ONE,
        fallback_policy=FallbackPolicy.ALLOW_RAW_STRING,
    )

    spec = ConstructionSpec(
        construction_id="copula_equative_classification",
        required_slots=(subject,),
        optional_slots=(profession,),
        description="Simple subject–classification clause.",
    )

    normalized_slot_map = spec.validate_slot_map(
        {
            "subject": {"label": "Marie Curie", "qid": "Q7186"},
            "profession": {"lemma": "physicist", "pos": "NOUN"},
        }
    )

The resulting `normalized_slot_map` is a canonical-name dict ready for the
later planning / realization pipeline.
"""

from __future__ import annotations

from dataclasses import MISSING, dataclass, field
from enum import Enum
import re
from typing import Any, Callable, Mapping, Optional, Sequence, TypeAlias


# ---------------------------------------------------------------------------
# JSON-ish shared aliases
# ---------------------------------------------------------------------------

JSONScalar: TypeAlias = None | bool | int | float | str
JSONValue: TypeAlias = JSONScalar | list["JSONValue"] | dict[str, "JSONValue"]
FeatureMap: TypeAlias = dict[str, Any]
MetadataMap: TypeAlias = dict[str, Any]
DefaultFactory: TypeAlias = Callable[[], Any]
SlotValidator: TypeAlias = Callable[[str, Any], None]


# ---------------------------------------------------------------------------
# Identifier rules
# ---------------------------------------------------------------------------

# Canonical runtime IDs and slot names are snake_case.
_RUNTIME_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_SLOT_NAME_RE = _RUNTIME_ID_RE

# Language code handling is intentionally permissive enough for:
#   en, fr, zh, pt_br, sr_latn, etc.
_LANG_CODE_RE = re.compile(r"^[a-z][a-z0-9_]*$")


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class SpecError(ValueError):
    """Base error for runtime spec validation failures."""


class InvalidIdentifierError(SpecError):
    """Raised when a runtime identifier is malformed."""


class SlotValidationError(SpecError):
    """Raised when a slot value does not satisfy its SlotSpec."""


class ConstructionSpecError(SpecError):
    """Raised when a ConstructionSpec is malformed or rejects a slot map."""


# ---------------------------------------------------------------------------
# Shared enums
# ---------------------------------------------------------------------------


class SlotValueKind(str, Enum):
    """
    Coarse runtime categories accepted by slot specifications.

    These are intentionally broad. They are not renderer-private node kinds.
    They describe the *runtime-level shape* of a slot value.
    """

    ANY = "any"
    ENTITY = "entity"
    LEXEME = "lexeme"
    EVENT = "event"
    TIME = "time"
    LOCATION = "location"
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    MAPPING = "mapping"
    LIST = "list"


class Cardinality(str, Enum):
    """
    Slot multiplicity rules.

    EXACTLY_ONE
        Required scalar value.

    ZERO_OR_ONE
        Optional scalar value.

    ONE_OR_MORE
        Required non-empty list.

    ZERO_OR_MORE
        Optional list (possibly empty).
    """

    EXACTLY_ONE = "exactly_one"
    ZERO_OR_ONE = "zero_or_one"
    ONE_OR_MORE = "one_or_more"
    ZERO_OR_MORE = "zero_or_more"

    @property
    def is_required(self) -> bool:
        return self in {Cardinality.EXACTLY_ONE, Cardinality.ONE_OR_MORE}

    @property
    def is_list_like(self) -> bool:
        return self in {Cardinality.ONE_OR_MORE, Cardinality.ZERO_OR_MORE}


class FallbackPolicy(str, Enum):
    """
    Explicit fallback behavior for slot values.

    FORBID
        No fallback beyond the accepted runtime kinds.

    ALLOW_NULL
        `None` may appear explicitly.

    ALLOW_RAW_STRING
        Bare strings are allowed as controlled fallback even when STRING is
        not listed in `accepted_kinds`.
    """

    FORBID = "forbid"
    ALLOW_NULL = "allow_null"
    ALLOW_RAW_STRING = "allow_raw_string"


# ---------------------------------------------------------------------------
# Shared normalization helpers
# ---------------------------------------------------------------------------


def normalize_non_empty_string(value: Any, field_name: str) -> str:
    """Return a stripped, non-empty string or raise."""
    if not isinstance(value, str):
        raise SpecError(f"{field_name} must be a string; got {type(value).__name__}.")
    out = value.strip()
    if not out:
        raise SpecError(f"{field_name} must not be empty.")
    return out


def normalize_optional_string(value: Any, field_name: str) -> Optional[str]:
    """Return a stripped string, None, or raise."""
    if value is None:
        return None
    return normalize_non_empty_string(value, field_name)


def normalize_runtime_id(value: Any, *, field_name: str = "runtime_id") -> str:
    """Normalize and validate a canonical snake_case runtime ID."""
    out = normalize_non_empty_string(value, field_name)
    if not _RUNTIME_ID_RE.fullmatch(out):
        raise InvalidIdentifierError(
            f"{field_name} must be canonical snake_case; got {value!r}."
        )
    return out


def normalize_slot_name(value: Any, *, field_name: str = "slot_name") -> str:
    """Normalize and validate a canonical snake_case slot name."""
    out = normalize_non_empty_string(value, field_name)
    if not _ SLOT_NAME_RE.fullmatch(out):
        raise InvalidIdentifierError(
            f"{field_name} must be canonical snake_case; got {value!r}."
        )
    return out


def normalize_lang_code(value: Any, *, field_name: str = "lang_code") -> str:
    """Normalize a runtime language code used by the planner/realizer path."""
    out = normalize_non_empty_string(value, field_name).lower()
    if not _LANG_CODE_RE.fullmatch(out):
        raise InvalidIdentifierError(
            f"{field_name} must be lowercase runtime-safe text; got {value!r}."
        )
    return out


def normalize_string_tuple(values: Optional[Sequence[str]]) -> tuple[str, ...]:
    """Normalize a possibly-null string sequence into a deduplicated tuple."""
    if not values:
        return ()
    seen: set[str] = set()
    out: list[str] = []
    for raw in values:
        item = normalize_non_empty_string(raw, "sequence_item")
        if item not in seen:
            out.append(item)
            seen.add(item)
    return tuple(out)


def ensure_mapping(value: Any, *, field_name: str) -> Mapping[str, Any]:
    """Require a mapping-like object."""
    if not isinstance(value, Mapping):
        raise SpecError(f"{field_name} must be a mapping; got {type(value).__name__}.")
    return value


def ensure_feature_map(value: Any, *, field_name: str = "features") -> FeatureMap:
    """Require a JSON-serializable-ish feature mapping and return a plain dict."""
    mapping = ensure_mapping(value, field_name=field_name)
    return {str(k): v for k, v in mapping.items()}


def merge_feature_maps(
    *maps: Optional[Mapping[str, Any]],
    prefer_rightmost: bool = True,
) -> FeatureMap:
    """
    Merge feature maps into a new plain dict.

    By default, later maps win. Set `prefer_rightmost=False` to keep the first
    value seen for any key.
    """
    merged: FeatureMap = {}
    for mapping in maps:
        if not mapping:
            continue
        for key, value in mapping.items():
            skey = str(key)
            if prefer_rightmost or skey not in merged:
                merged[skey] = value
    return merged


# ---------------------------------------------------------------------------
# Slot-value shape inference
# ---------------------------------------------------------------------------


def infer_slot_value_kind(value: Any) -> SlotValueKind:
    """
    Infer a coarse runtime kind from a slot value.

    Heuristics intentionally stay shallow and stable. They are used only for
    spec validation, not for deep semantic interpretation.
    """
    if isinstance(value, bool):
        return SlotValueKind.BOOLEAN
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return SlotValueKind.NUMBER
    if isinstance(value, str):
        return SlotValueKind.STRING
    if isinstance(value, (list, tuple)):
        return SlotValueKind.LIST
    if isinstance(value, Mapping):
        keys = {str(k) for k in value.keys()}

        # Common entity-ref indicators
        if keys & {"entity_id", "qid", "entity_type", "label", "name"}:
            # Keep location more specific where possible.
            if keys & {"location_type", "country_code", "geo", "coordinates"}:
                return SlotValueKind.LOCATION
            return SlotValueKind.ENTITY

        # Common lexeme-ref / lexical-value indicators
        if keys & {"lexeme_id", "lemma", "pos", "sense", "surface"}:
            return SlotValueKind.LEXEME

        # Common event indicators
        if keys & {"event_id", "event_type", "participants", "time"}:
            return SlotValueKind.EVENT

        # Common time-span indicators
        if keys & {"start_year", "end_year", "start", "end", "approximate"}:
            return SlotValueKind.TIME

        return SlotValueKind.MAPPING

    return SlotValueKind.ANY


# ---------------------------------------------------------------------------
# SlotSpec
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SlotSpec:
    """
    Declarative contract for one construction slot.

    Notes
    -----
    - This spec governs validation and normalization only.
    - It does not own realized text, backend payloads, or AST fragments.
    - Use aliases only for compatibility at ingestion boundaries.
      Canonical slot-map output always uses `name`.
    """

    name: str
    accepted_kinds: tuple[SlotValueKind, ...] = (SlotValueKind.ANY,)
    cardinality: Cardinality = Cardinality.ZERO_OR_ONE
    fallback_policy: FallbackPolicy = FallbackPolicy.FORBID

    # If a mapping contains `features`, these keys are the preferred/allowed
    # feature names for this slot when strict feature checking is enabled.
    expected_feature_keys: frozenset[str] = frozenset()
    allow_extra_features: bool = True

    # Compatibility aliases accepted on input.
    aliases: tuple[str, ...] = ()

    # Optional description/examples/metadata for registry, docs, and debugging.
    description: Optional[str] = None
    examples: tuple[Any, ...] = ()
    metadata: MetadataMap = field(default_factory=dict)

    # Defaulting: exactly one of `default` or `default_factory` may be used.
    default: Any = MISSING
    default_factory: Optional[DefaultFactory] = field(
        default=None,
        repr=False,
        compare=False,
    )

    # Optional caller-supplied validator hook.
    validator: Optional[SlotValidator] = field(
        default=None,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        canonical_name = normalize_slot_name(self.name, field_name="SlotSpec.name")
        object.__setattr__(self, "name", canonical_name)

        normalized_aliases = tuple(
            normalize_slot_name(alias, field_name=f"SlotSpec.alias({canonical_name})")
            for alias in self.aliases
        )
        if canonical_name in normalized_aliases:
            raise ConstructionSpecError(
                f"SlotSpec {canonical_name!r} must not list itself as an alias."
            )
        if len(set(normalized_aliases)) != len(normalized_aliases):
            raise ConstructionSpecError(
                f"SlotSpec {canonical_name!r} contains duplicate aliases."
            )
        object.__setattr__(self, "aliases", normalized_aliases)

        kinds = tuple(self.accepted_kinds) if self.accepted_kinds else (SlotValueKind.ANY,)
        if SlotValueKind.ANY in kinds and len(kinds) > 1:
            kinds = (SlotValueKind.ANY,)
        object.__setattr__(self, "accepted_kinds", _dedupe_enum_tuple(kinds))

        feature_keys = frozenset(
            normalize_non_empty_string(k, f"{canonical_name}.expected_feature_keys")
            for k in self.expected_feature_keys
        )
        object.__setattr__(self, "expected_feature_keys", feature_keys)

        desc = normalize_optional_string(self.description, f"{canonical_name}.description")
        object.__setattr__(self, "description", desc)

        if self.default is not MISSING and self.default_factory is not None:
            raise ConstructionSpecError(
                f"SlotSpec {canonical_name!r} cannot define both default and default_factory."
            )

        if self.cardinality.is_list_like:
            if self.default is not MISSING and self.default is not None and not isinstance(self.default, list):
                raise ConstructionSpecError(
                    f"SlotSpec {canonical_name!r} has list cardinality but non-list default."
                )

        # Shallow-copy metadata for safer construction-time isolation.
        object.__setattr__(self, "metadata", dict(self.metadata))

        # Validate any literal default at construction time.
        if self.default is not MISSING:
            self.validate_value(self.default)

    @property
    def canonical_names(self) -> tuple[str, ...]:
        """Canonical name followed by accepted aliases."""
        return (self.name, *self.aliases)

    @property
    def is_required(self) -> bool:
        """Whether a value must exist for this slot."""
        return self.cardinality.is_required

    @property
    def is_list_like(self) -> bool:
        """Whether the slot expects a list value."""
        return self.cardinality.is_list_like

    def matches_name(self, raw_name: str) -> bool:
        """True when `raw_name` resolves to this slot (canonical or alias)."""
        try:
            norm = normalize_slot_name(raw_name, field_name="slot_name")
        except SpecError:
            return False
        return norm in self.canonical_names

    def has_default(self) -> bool:
        """Whether a missing slot can be defaulted."""
        return self.default is not MISSING or self.default_factory is not None

    def get_default_value(self) -> Any:
        """
        Return a fresh default value where possible.

        For repeated slots, default to [] when no explicit default/default_factory
        exists and the slot is optional.
        """
        if self.default_factory is not None:
            value = self.default_factory()
            self.validate_value(value)
            return value

        if self.default is not MISSING:
            return self.default

        if self.cardinality == Cardinality.ZERO_OR_MORE:
            return []

        return None

    def accepts_kind(self, kind: SlotValueKind) -> bool:
        """Whether this spec accepts the inferred runtime kind."""
        return SlotValueKind.ANY in self.accepted_kinds or kind in self.accepted_kinds

    def validate_value(self, value: Any) -> None:
        """
        Validate a slot value against this SlotSpec.

        Raises
        ------
        SlotValidationError
            If the value is incompatible with the slot contract.
        """
        if value is None:
            if self.is_required and self.fallback_policy != FallbackPolicy.ALLOW_NULL:
                raise SlotValidationError(
                    f"Slot {self.name!r} is required and does not allow null."
                )
            return

        if self.is_list_like:
            if not isinstance(value, list):
                raise SlotValidationError(
                    f"Slot {self.name!r} requires a list value; got {type(value).__name__}."
                )
            if self.cardinality == Cardinality.ONE_OR_MORE and not value:
                raise SlotValidationError(
                    f"Slot {self.name!r} requires at least one list item."
                )
            for idx, item in enumerate(value):
                self._validate_single_value(item, path=f"{self.name}[{idx}]")
            return

        self._validate_single_value(value, path=self.name)

    def _validate_single_value(self, value: Any, *, path: str) -> None:
        if value is None:
            if self.fallback_policy != FallbackPolicy.ALLOW_NULL:
                raise SlotValidationError(f"{path} does not allow null.")
            return

        kind = infer_slot_value_kind(value)

        # Raw-string fallback may be allowed even when STRING is not an accepted kind.
        if isinstance(value, str) and not self.accepts_kind(SlotValueKind.STRING):
            if self.fallback_policy != FallbackPolicy.ALLOW_RAW_STRING:
                raise SlotValidationError(
                    f"{path} rejects raw string fallback."
                )
        elif not self.accepts_kind(kind):
            raise SlotValidationError(
                f"{path} expected kind(s) {[k.value for k in self.accepted_kinds]!r}; "
                f"got {kind.value!r}."
            )

        if isinstance(value, Mapping):
            self._validate_mapping_shape(value, path=path)

        if self.validator is not None:
            self.validator(self.name, value)

    def _validate_mapping_shape(self, value: Mapping[str, Any], *, path: str) -> None:
        if "features" not in value:
            return

        raw_features = value["features"]
        if not isinstance(raw_features, Mapping):
            raise SlotValidationError(f"{path}.features must be a mapping.")

        if not self.expected_feature_keys:
            return

        provided = {str(k) for k in raw_features.keys()}
        unknown = sorted(provided - self.expected_feature_keys)
        if unknown and not self.allow_extra_features:
            raise SlotValidationError(
                f"{path}.features contains unsupported keys: {unknown!r}. "
                f"Allowed: {sorted(self.expected_feature_keys)!r}."
            )

    def normalize_missing(self) -> Any:
        """
        Return the normalized value for an omitted slot.

        Required slots without defaults remain missing and must be handled by
        the caller as an error.
        """
        if self.has_default():
            return self.get_default_value()
        if self.cardinality == Cardinality.ZERO_OR_MORE:
            return []
        return None


# ---------------------------------------------------------------------------
# ConstructionSpec
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ConstructionSpec:
    """
    Declarative contract for one canonical runtime construction.

    The registry owns instances of this type. The slot map itself does not
    define these rules; it merely carries values.
    """

    construction_id: str
    required_slots: tuple[SlotSpec, ...] = ()
    optional_slots: tuple[SlotSpec, ...] = ()

    description: Optional[str] = None
    tags: tuple[str, ...] = ()
    metadata: MetadataMap = field(default_factory=dict)

    # If False, incoming slot maps may only contain declared slots/aliases.
    allow_extra_slots: bool = False

    def __post_init__(self) -> None:
        cid = normalize_runtime_id(
            self.construction_id,
            field_name="ConstructionSpec.construction_id",
        )
        object.__setattr__(self, "construction_id", cid)

        required = tuple(self.required_slots)
        optional = tuple(self.optional_slots)

        seen_names: dict[str, str] = {}
        for group_name, specs in (("required_slots", required), ("optional_slots", optional)):
            for spec in specs:
                if not isinstance(spec, SlotSpec):
                    raise ConstructionSpecError(
                        f"{cid}.{group_name} must contain SlotSpec instances."
                    )
                for name in spec.canonical_names:
                    if name in seen_names:
                        prev = seen_names[name]
                        raise ConstructionSpecError(
                            f"{cid} contains conflicting slot/alias name {name!r} "
                            f"between {prev!r} and {spec.name!r}."
                        )
                    seen_names[name] = spec.name

        overlap = {s.name for s in required} & {s.name for s in optional}
        if overlap:
            raise ConstructionSpecError(
                f"{cid} declares the same slot as both required and optional: {sorted(overlap)!r}."
            )

        object.__setattr__(self, "required_slots", required)
        object.__setattr__(self, "optional_slots", optional)
        object.__setattr__(self, "tags", normalize_string_tuple(self.tags))
        object.__setattr__(self, "description", normalize_optional_string(self.description, f"{cid}.description"))
        object.__setattr__(self, "metadata", dict(self.metadata))

    @property
    def all_slots(self) -> tuple[SlotSpec, ...]:
        """All declared slots in canonical order: required first, then optional."""
        return (*self.required_slots, *self.optional_slots)

    @property
    def required_slot_names(self) -> tuple[str, ...]:
        """Canonical names of required slots."""
        return tuple(spec.name for spec in self.required_slots)

    @property
    def optional_slot_names(self) -> tuple[str, ...]:
        """Canonical names of optional slots."""
        return tuple(spec.name for spec in self.optional_slots)

    def get_slot(self, name: str) -> Optional[SlotSpec]:
        """Resolve a canonical or alias slot name to its SlotSpec."""
        try:
            norm = normalize_slot_name(name, field_name="slot_name")
        except SpecError:
            return None

        for spec in self.all_slots:
            if norm in spec.canonical_names:
                return spec
        return None

    def resolve_slot_name(self, name: str) -> Optional[str]:
        """Resolve a raw slot name/alias to the canonical name."""
        spec = self.get_slot(name)
        return None if spec is None else spec.name

    def validate_slot_map(self, slot_map: Mapping[str, Any]) -> dict[str, Any]:
        """
        Validate and canonicalize a slot map against this construction spec.

        Returns
        -------
        dict[str, Any]
            A new plain dict whose keys are canonical slot names.

        Raises
        ------
        ConstructionSpecError
            For unknown slots, alias collisions, or missing required slots.

        SlotValidationError
            When a provided slot value fails its SlotSpec.
        """
        incoming = ensure_mapping(slot_map, field_name=f"{self.construction_id}.slot_map")
        normalized: dict[str, Any] = {}
        unknown: list[str] = []

        for raw_name, value in incoming.items():
            raw_name_str = str(raw_name)
            spec = self.get_slot(raw_name_str)
            if spec is None:
                if self.allow_extra_slots:
                    normalized[raw_name_str] = value
                    continue
                unknown.append(raw_name_str)
                continue

            canonical_name = spec.name
            if canonical_name in normalized:
                raise ConstructionSpecError(
                    f"{self.construction_id} received duplicate values for "
                    f"slot {canonical_name!r} (possibly via alias + canonical name)."
                )

            spec.validate_value(value)
            normalized[canonical_name] = value

        if unknown:
            raise ConstructionSpecError(
                f"{self.construction_id} received unknown slot(s): {sorted(unknown)!r}."
            )

        for spec in self.required_slots:
            if spec.name not in normalized:
                if spec.has_default():
                    normalized[spec.name] = spec.get_default_value()
                else:
                    raise ConstructionSpecError(
                        f"{self.construction_id} is missing required slot {spec.name!r}."
                    )

        for spec in self.optional_slots:
            if spec.name not in normalized and spec.has_default():
                normalized[spec.name] = spec.get_default_value()

        return normalized

    def supports_slot(self, name: str) -> bool:
        """True when the construction declares the given canonical/alias slot."""
        return self.get_slot(name) is not None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _dedupe_enum_tuple(values: Sequence[SlotValueKind]) -> tuple[SlotValueKind, ...]:
    seen: set[SlotValueKind] = set()
    out: list[SlotValueKind] = []
    for item in values:
        if item not in seen:
            out.append(item)
            seen.add(item)
    return tuple(out)


# ---------------------------------------------------------------------------
# Public exports
# ---------------------------------------------------------------------------

__all__ = [
    # aliases
    "JSONScalar",
    "JSONValue",
    "FeatureMap",
    "MetadataMap",
    "DefaultFactory",
    "SlotValidator",
    # errors
    "SpecError",
    "InvalidIdentifierError",
    "SlotValidationError",
    "ConstructionSpecError",
    # enums
    "SlotValueKind",
    "Cardinality",
    "FallbackPolicy",
    # dataclasses
    "SlotSpec",
    "ConstructionSpec",
    # helpers
    "normalize_non_empty_string",
    "normalize_optional_string",
    "normalize_runtime_id",
    "normalize_slot_name",
    "normalize_lang_code",
    "normalize_string_tuple",
    "ensure_mapping",
    "ensure_feature_map",
    "merge_feature_maps",
    "infer_slot_value_kind",
]