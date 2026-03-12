# app/core/domain/planning/construction_plan.py
from __future__ import annotations

"""
Canonical renderer-facing construction plan.

This module defines :class:`ConstructionPlan`, the shared runtime object that
bridges planning / slot-building and realization.

Design goals
============
- Construction-generic, not biography-shaped.
- Backend-agnostic: the same plan can be consumed by GF, family, or safe-mode.
- Immutable by default to reduce accidental cross-stage mutation.
- Compatible with migration-era dict-based slot maps.
- Strict about plan-level vs slot-level boundaries.

Contract highlights
===================
Required fields:
    - construction_id
    - lang_code
    - slot_map
    - generation_options

Optional plan-level fields:
    - topic_entity_id
    - focus_role
    - lexical_bindings
    - provenance

Compatibility:
    - Older code may still pass plain dict slot maps.
    - Planner metadata may still be carried while migration is in progress.

Important boundary rule:
    Reserved plan-level names MUST NOT appear as slot keys.
"""

from dataclasses import asdict, dataclass, field, is_dataclass, replace
from types import MappingProxyType
from typing import Any, Iterable, Iterator, Mapping
from collections.abc import Mapping as ABCMapping

__all__ = ["ConstructionPlan"]


# ---------------------------------------------------------------------------
# Reserved top-level names
# ---------------------------------------------------------------------------

_RESERVED_PLAN_LEVEL_FIELDS: frozenset[str] = frozenset(
    {
        "construction_id",
        "lang_code",
        "generation_options",
        "topic_entity_id",
        "focus_role",
        "lexical_bindings",
        "provenance",
    }
)


# ---------------------------------------------------------------------------
# Small normalization / freezing helpers
# ---------------------------------------------------------------------------


def _normalize_required_str(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string, got {type(value).__name__}.")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must be a non-empty string.")
    return normalized


def _normalize_optional_str(value: Any, *, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string or None, got {type(value).__name__}.")
    normalized = value.strip()
    return normalized or None


def _materialize_mapping(value: Any, *, field_name: str) -> dict[str, Any]:
    """
    Normalize a mapping-like value into a plain dict.

    Accepted shapes:
    - standard Mapping
    - objects exposing `.to_dict()`
    - objects exposing `.as_dict()`
    - dataclasses (converted via `asdict`)
    """
    if value is None:
        return {}

    if hasattr(value, "to_dict") and callable(value.to_dict):
        value = value.to_dict()
    elif hasattr(value, "as_dict") and callable(value.as_dict):
        value = value.as_dict()
    elif is_dataclass(value):
        value = asdict(value)

    if not isinstance(value, ABCMapping):
        raise TypeError(f"{field_name} must be mapping-like, got {type(value).__name__}.")

    out: dict[str, Any] = {}
    for raw_key, raw_val in value.items():
        if not isinstance(raw_key, str):
            raise TypeError(
                f"{field_name} keys must be strings, got {type(raw_key).__name__}."
            )
        key = raw_key.strip()
        if not key:
            raise ValueError(f"{field_name} contains an empty key.")
        out[key] = raw_val
    return out


def _freeze_jsonish(value: Any) -> Any:
    """
    Recursively freeze common JSON-like structures.

    - dict/mapping -> MappingProxyType
    - list/tuple -> tuple
    - set/frozenset -> frozenset
    - dataclass -> frozen dict-like mapping
    - scalars / unknown objects -> unchanged
    """
    if is_dataclass(value):
        value = asdict(value)

    if isinstance(value, ABCMapping):
        return MappingProxyType({str(k): _freeze_jsonish(v) for k, v in value.items()})

    if isinstance(value, list | tuple):
        return tuple(_freeze_jsonish(v) for v in value)

    if isinstance(value, set | frozenset):
        return frozenset(_freeze_jsonish(v) for v in value)

    return value


def _thaw_jsonish(value: Any) -> Any:
    """
    Convert recursively frozen values back into plain JSON-friendly Python
    containers.
    """
    if isinstance(value, MappingProxyType):
        value = dict(value)

    if isinstance(value, ABCMapping):
        return {str(k): _thaw_jsonish(v) for k, v in value.items()}

    if isinstance(value, tuple):
        return [_thaw_jsonish(v) for v in value]

    if isinstance(value, frozenset):
        return [_thaw_jsonish(v) for v in value]

    return value


def _validate_slot_map(slot_map: Mapping[str, Any]) -> None:
    """
    Validate only the generic slot-map contract.

    Construction-specific required-role validation belongs elsewhere
    (registry / builder / selector layers), not here.
    """
    if not isinstance(slot_map, ABCMapping):
        raise TypeError("slot_map must be a mapping.")

    for key in slot_map.keys():
        if not isinstance(key, str):
            raise TypeError("slot_map keys must be strings.")
        if not key.strip():
            raise ValueError("slot_map contains an empty slot name.")
        if key in _RESERVED_PLAN_LEVEL_FIELDS:
            raise ValueError(
                f"slot_map contains reserved plan-level field {key!r}; "
                "keep plan-level fields outside the slot map."
            )


def _validate_generic_mapping_keys(value: Mapping[str, Any], *, field_name: str) -> None:
    for key in value.keys():
        if not isinstance(key, str):
            raise TypeError(f"{field_name} keys must be strings.")
        if not key.strip():
            raise ValueError(f"{field_name} contains an empty key.")


# ---------------------------------------------------------------------------
# ConstructionPlan
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ConstructionPlan:
    """
    Canonical renderer-facing runtime object.

    A `ConstructionPlan` represents one clause/sentence realization unit after
    planning and slot-building, and before backend realization.

    Notes
    -----
    * The planner chooses what sentence is to be said.
    * The renderer chooses how the selected backend realizes it.
    * This object sits exactly at that boundary.
    """

    construction_id: str
    lang_code: str
    slot_map: Mapping[str, Any]
    generation_options: Mapping[str, Any] = field(default_factory=dict)

    topic_entity_id: str | None = None
    focus_role: str | None = None

    lexical_bindings: Mapping[str, Any] = field(default_factory=dict)
    provenance: Mapping[str, Any] = field(default_factory=dict)

    # Kept for migration / diagnostics / wrapper metadata such as:
    # {"wrapper_construction_id": "...", "base_construction_id": "..."}
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        construction_id = _normalize_required_str(
            self.construction_id,
            field_name="construction_id",
        )
        lang_code = _normalize_required_str(self.lang_code, field_name="lang_code")
        topic_entity_id = _normalize_optional_str(
            self.topic_entity_id,
            field_name="topic_entity_id",
        )
        focus_role = _normalize_optional_str(self.focus_role, field_name="focus_role")

        slot_map = _materialize_mapping(self.slot_map, field_name="slot_map")
        generation_options = _materialize_mapping(
            self.generation_options,
            field_name="generation_options",
        )
        lexical_bindings = _materialize_mapping(
            self.lexical_bindings,
            field_name="lexical_bindings",
        )
        provenance = _materialize_mapping(self.provenance, field_name="provenance")
        metadata = _materialize_mapping(self.metadata, field_name="metadata")

        _validate_slot_map(slot_map)
        _validate_generic_mapping_keys(generation_options, field_name="generation_options")
        _validate_generic_mapping_keys(lexical_bindings, field_name="lexical_bindings")
        _validate_generic_mapping_keys(provenance, field_name="provenance")
        _validate_generic_mapping_keys(metadata, field_name="metadata")

        object.__setattr__(self, "construction_id", construction_id)
        object.__setattr__(self, "lang_code", lang_code)
        object.__setattr__(self, "topic_entity_id", topic_entity_id)
        object.__setattr__(self, "focus_role", focus_role)
        object.__setattr__(self, "slot_map", _freeze_jsonish(slot_map))
        object.__setattr__(self, "generation_options", _freeze_jsonish(generation_options))
        object.__setattr__(self, "lexical_bindings", _freeze_jsonish(lexical_bindings))
        object.__setattr__(self, "provenance", _freeze_jsonish(provenance))
        object.__setattr__(self, "metadata", _freeze_jsonish(metadata))

    # ------------------------------------------------------------------
    # Basic container-like helpers
    # ------------------------------------------------------------------

    def __contains__(self, slot_name: object) -> bool:
        return slot_name in self.slot_map

    def __getitem__(self, slot_name: str) -> Any:
        return self.slot_map[slot_name]

    def __iter__(self) -> Iterator[str]:
        return iter(self.slot_map)

    def __len__(self) -> int:
        return len(self.slot_map)

    @property
    def slot_keys(self) -> tuple[str, ...]:
        return tuple(self.slot_map.keys())

    @property
    def is_wrapper_plan(self) -> bool:
        return "wrapper_construction_id" in self.metadata

    @property
    def wrapper_construction_id(self) -> str | None:
        value = self.metadata.get("wrapper_construction_id")
        return value if isinstance(value, str) and value.strip() else None

    @property
    def base_construction_id(self) -> str:
        value = self.metadata.get("base_construction_id")
        if isinstance(value, str) and value.strip():
            return value.strip()
        return self.construction_id

    def has_slot(self, slot_name: str) -> bool:
        return slot_name in self.slot_map

    def get_slot(self, slot_name: str, default: Any = None) -> Any:
        return self.slot_map.get(slot_name, default)

    # ------------------------------------------------------------------
    # Validation / serialization
    # ------------------------------------------------------------------

    @classmethod
    def reserved_plan_level_fields(cls) -> frozenset[str]:
        return _RESERVED_PLAN_LEVEL_FIELDS

    def validate(self) -> ConstructionPlan:
        """
        Re-run basic generic validation.

        This is mainly useful for explicit call sites and tests; construction-
        specific role validation still belongs to higher-level registries.
        """
        _validate_slot_map(self.slot_map)
        _validate_generic_mapping_keys(
            self.generation_options,
            field_name="generation_options",
        )
        _validate_generic_mapping_keys(
            self.lexical_bindings,
            field_name="lexical_bindings",
        )
        _validate_generic_mapping_keys(self.provenance, field_name="provenance")
        _validate_generic_mapping_keys(self.metadata, field_name="metadata")
        return self

    def to_dict(self, *, include_empty: bool = False) -> dict[str, Any]:
        """
        Serialize into a plain Python dict.

        Parameters
        ----------
        include_empty:
            If False, omit empty optional dict-like fields. Required fields are
            always emitted.
        """
        out: dict[str, Any] = {
            "construction_id": self.construction_id,
            "lang_code": self.lang_code,
            "slot_map": _thaw_jsonish(self.slot_map),
            "generation_options": _thaw_jsonish(self.generation_options),
        }

        if self.topic_entity_id is not None:
            out["topic_entity_id"] = self.topic_entity_id
        if self.focus_role is not None:
            out["focus_role"] = self.focus_role

        lexical_bindings = _thaw_jsonish(self.lexical_bindings)
        provenance = _thaw_jsonish(self.provenance)
        metadata = _thaw_jsonish(self.metadata)

        if include_empty or lexical_bindings:
            out["lexical_bindings"] = lexical_bindings
        if include_empty or provenance:
            out["provenance"] = provenance
        if include_empty or metadata:
            out["metadata"] = metadata

        return out

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ConstructionPlan:
        """
        Build a `ConstructionPlan` from a plain mapping.

        Unknown keys are ignored intentionally so callers can pass legacy /
        richer envelopes and normalize them upstream over time.
        """
        if not isinstance(data, ABCMapping):
            raise TypeError("ConstructionPlan.from_dict expects a mapping.")

        return cls(
            construction_id=data.get("construction_id"),
            lang_code=data.get("lang_code"),
            slot_map=data.get("slot_map", {}),
            generation_options=data.get("generation_options", {}),
            topic_entity_id=data.get("topic_entity_id"),
            focus_role=data.get("focus_role"),
            lexical_bindings=data.get("lexical_bindings", {}),
            provenance=data.get("provenance", {}),
            metadata=data.get("metadata", {}),
        )

    # ------------------------------------------------------------------
    # Immutable update helpers
    # ------------------------------------------------------------------

    def with_slot_map(self, slot_map: Mapping[str, Any]) -> ConstructionPlan:
        return replace(self, slot_map=slot_map)

    def with_slot(self, slot_name: str, value: Any) -> ConstructionPlan:
        slot_name = _normalize_required_str(slot_name, field_name="slot_name")
        updated = dict(_thaw_jsonish(self.slot_map))
        updated[slot_name] = value
        return replace(self, slot_map=updated)

    def without_slot(self, slot_name: str) -> ConstructionPlan:
        updated = dict(_thaw_jsonish(self.slot_map))
        updated.pop(slot_name, None)
        return replace(self, slot_map=updated)

    def with_slots(self, **updates: Any) -> ConstructionPlan:
        updated = dict(_thaw_jsonish(self.slot_map))
        for key, value in updates.items():
            normalized_key = _normalize_required_str(key, field_name="slot_name")
            updated[normalized_key] = value
        return replace(self, slot_map=updated)

    def with_generation_options(
        self,
        options: Mapping[str, Any] | None = None,
        /,
        **updates: Any,
    ) -> ConstructionPlan:
        merged = dict(_thaw_jsonish(self.generation_options))
        if options:
            merged.update(_materialize_mapping(options, field_name="generation_options"))
        merged.update(updates)
        return replace(self, generation_options=merged)

    def with_lexical_bindings(
        self,
        bindings: Mapping[str, Any] | None = None,
        /,
        **updates: Any,
    ) -> ConstructionPlan:
        merged = dict(_thaw_jsonish(self.lexical_bindings))
        if bindings:
            merged.update(_materialize_mapping(bindings, field_name="lexical_bindings"))
        merged.update(updates)
        return replace(self, lexical_bindings=merged)

    def with_provenance(
        self,
        provenance: Mapping[str, Any] | None = None,
        /,
        **updates: Any,
    ) -> ConstructionPlan:
        merged = dict(_thaw_jsonish(self.provenance))
        if provenance:
            merged.update(_materialize_mapping(provenance, field_name="provenance"))
        merged.update(updates)
        return replace(self, provenance=merged)

    def with_metadata(
        self,
        metadata: Mapping[str, Any] | None = None,
        /,
        **updates: Any,
    ) -> ConstructionPlan:
        merged = dict(_thaw_jsonish(self.metadata))
        if metadata:
            merged.update(_materialize_mapping(metadata, field_name="metadata"))
        merged.update(updates)
        return replace(self, metadata=merged)

    def with_discourse(
        self,
        *,
        topic_entity_id: str | None = None,
        focus_role: str | None = None,
    ) -> ConstructionPlan:
        return replace(
            self,
            topic_entity_id=topic_entity_id,
            focus_role=focus_role,
        )

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def summary(self) -> dict[str, Any]:
        """
        Compact machine-readable summary useful for logs and debug traces.
        """
        return {
            "construction_id": self.construction_id,
            "lang_code": self.lang_code,
            "slot_keys": list(self.slot_keys),
            "topic_entity_id": self.topic_entity_id,
            "focus_role": self.focus_role,
            "has_lexical_bindings": bool(self.lexical_bindings),
            "is_wrapper_plan": self.is_wrapper_plan,
            "base_construction_id": self.base_construction_id,
        }

    def required_slots_present(self, required_slots: Iterable[str]) -> bool:
        """
        Convenience helper for registries / tests that want a quick required-slot
        presence check without coupling that logic into the base dataclass.
        """
        return all(slot in self.slot_map for slot in required_slots)