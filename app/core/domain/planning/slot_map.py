from __future__ import annotations

"""
Canonical semantic slot map contract for planner/runtime generation.

A SlotMap is the renderer-facing mapping from semantic role names
(`subject`, `profession`, `location`, ...) to semantic values. It is
deliberately construction-generic and backend-neutral.

Design goals
------------
- Immutable-by-contract: later stages must not mutate shared slot state.
- Stable ordering: slot iteration preserves insertion order for debugging,
  reproducibility, and deterministic downstream behavior.
- Plan-level separation: construction metadata such as `construction_id`
  and `lang_code` must *not* live inside the slot map.
- Semantics first: values may be literals, semantic dataclasses, typed refs,
  or structured semantic payloads; renderer-private data does not belong here.

This module intentionally does not impose a bio-specific value schema.
Constructions and lexical resolution may progressively narrow generic semantic
values into more specific typed references.
"""

import copy
import dataclasses
import math
from dataclasses import asdict
from datetime import date, datetime, time
from enum import Enum
from types import MappingProxyType
from typing import Any, Iterable, Iterator, Mapping, Sequence, TypeAlias


SlotName: TypeAlias = str
SlotValue: TypeAlias = Any


class SlotMapError(ValueError):
    """Base error for slot-map validation and access problems."""


class InvalidSlotNameError(SlotMapError):
    """Raised when a slot name is empty, reserved, or otherwise invalid."""


class InvalidSlotValueError(SlotMapError):
    """Raised when a slot value cannot participate in the canonical contract."""


class MissingRequiredSlotError(SlotMapError):
    """Raised when a required slot is missing (or unexpectedly null)."""


_RESERVED_PLAN_LEVEL_FIELDS = frozenset(
    {
        "construction_id",
        "lang_code",
        "generation_options",
        "topic_entity_id",
        "focus_role",
        "lexical_bindings",
        "provenance",
        "debug_info",
    }
)


def _is_dataclass_instance(value: Any) -> bool:
    return dataclasses.is_dataclass(value) and not isinstance(value, type)


def _validate_slot_name(name: str) -> str:
    if not isinstance(name, str):
        raise InvalidSlotNameError(f"Slot names must be strings, got {type(name)!r}.")
    if not name:
        raise InvalidSlotNameError("Slot names must not be empty.")
    if name.strip() != name:
        raise InvalidSlotNameError(
            f"Slot name {name!r} must not contain surrounding whitespace."
        )
    if any(ch.isspace() for ch in name):
        raise InvalidSlotNameError(
            f"Slot name {name!r} must not contain internal whitespace."
        )
    if name in _RESERVED_PLAN_LEVEL_FIELDS:
        raise InvalidSlotNameError(
            f"Slot name {name!r} is reserved for ConstructionPlan-level metadata."
        )
    return name


def _freeze_value(value: Any, *, path: str) -> Any:
    """
    Create a deterministic, non-shared snapshot of a slot value.

    Rules
    -----
    - primitives are preserved
    - lists/tuples become tuples
    - mappings become read-only MappingProxyType snapshots
    - dataclass / model objects are deep-copied
    - sets are rejected because they destroy deterministic ordering
    - callables / binary blobs are rejected because they do not belong in
      a semantic runtime contract
    """
    if value is None or isinstance(value, (str, bool, int)):
        return value

    if isinstance(value, float):
        if not math.isfinite(value):
            raise InvalidSlotValueError(
                f"Non-finite float at {path} is not allowed in SlotMap: {value!r}."
            )
        return value

    if isinstance(value, Enum):
        return _freeze_value(value.value, path=path)

    if isinstance(value, (bytes, bytearray, memoryview)):
        raise InvalidSlotValueError(
            f"Binary data at {path} is not allowed in SlotMap."
        )

    if callable(value):
        raise InvalidSlotValueError(
            f"Callable value at {path} is not allowed in SlotMap."
        )

    if isinstance(value, Mapping):
        frozen: dict[str, Any] = {}
        for raw_key, raw_val in value.items():
            if not isinstance(raw_key, str):
                raise InvalidSlotValueError(
                    f"Nested mapping keys at {path} must be strings, got {type(raw_key)!r}."
                )
            frozen[raw_key] = _freeze_value(raw_val, path=f"{path}.{raw_key}")
        return MappingProxyType(frozen)

    if isinstance(value, (list, tuple)):
        return tuple(
            _freeze_value(item, path=f"{path}[{index}]")
            for index, item in enumerate(value)
        )

    if isinstance(value, (set, frozenset)):
        raise InvalidSlotValueError(
            f"Set-like value at {path} is not allowed because slot ordering must stay deterministic."
        )

    try:
        return copy.deepcopy(value)
    except Exception as exc:  # pragma: no cover - defensive branch
        raise InvalidSlotValueError(
            f"Value at {path} of type {type(value)!r} could not be safely copied."
        ) from exc


def _thaw_value(value: Any) -> Any:
    """Return a mutable Python representation of a frozen slot value."""
    if isinstance(value, Mapping):
        return {k: _thaw_value(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [_thaw_value(v) for v in value]
    try:
        return copy.deepcopy(value)
    except Exception:  # pragma: no cover - defensive branch
        return value


def _serialize_value(value: Any) -> Any:
    """
    Convert a slot value into a JSON-friendly diagnostic structure.

    This is intended for debug payloads and logging, not for canonical runtime
    storage. Unknown opaque objects are stringified as a last resort.
    """
    if value is None or isinstance(value, (str, bool, int)):
        return value

    if isinstance(value, float):
        return value if math.isfinite(value) else None

    if isinstance(value, Enum):
        return _serialize_value(value.value)

    if isinstance(value, (date, datetime, time)):
        return value.isoformat()

    if isinstance(value, Mapping):
        return {k: _serialize_value(v) for k, v in value.items()}

    if isinstance(value, tuple):
        return [_serialize_value(v) for v in value]

    if _is_dataclass_instance(value):
        return _serialize_value(asdict(value))

    if hasattr(value, "model_dump") and callable(value.model_dump):
        try:
            return _serialize_value(value.model_dump())
        except Exception:
            return repr(value)

    if hasattr(value, "dict") and callable(value.dict):
        try:
            return _serialize_value(value.dict())
        except Exception:
            return repr(value)

    return repr(value)


@dataclasses.dataclass(frozen=True, slots=True, init=False, eq=False)
class SlotMap(Mapping[str, SlotValue]):
    """
    Immutable, ordered mapping of semantic slot names to semantic values.

    Notes
    -----
    - SlotMap contains only semantic role data.
    - Plan-level metadata belongs in ConstructionPlan, not here.
    - Later stages may derive debug output from SlotMap, but must not store
      debug payloads inside it.
    """

    _items: tuple[tuple[str, SlotValue], ...]
    _index: dict[str, int]

    __hash__ = None

    def __init__(
        self,
        slots: Mapping[str, SlotValue] | Iterable[tuple[str, SlotValue]] | None = None,
    ) -> None:
        items_list: list[tuple[str, SlotValue]] = []
        index: dict[str, int] = {}

        if slots is None:
            slots_iter: Iterable[tuple[str, SlotValue]] = ()
        elif isinstance(slots, Mapping):
            slots_iter = slots.items()
        else:
            slots_iter = slots

        for raw_name, raw_value in slots_iter:
            name = _validate_slot_name(raw_name)
            frozen_value = _freeze_value(raw_value, path=name)

            if name in index:
                position = index[name]
                items_list[position] = (name, frozen_value)
            else:
                index[name] = len(items_list)
                items_list.append((name, frozen_value))

        object.__setattr__(self, "_items", tuple(items_list))
        object.__setattr__(self, "_index", index)

    @classmethod
    def empty(cls) -> "SlotMap":
        return cls()

    @classmethod
    def from_pairs(cls, *pairs: tuple[str, SlotValue]) -> "SlotMap":
        return cls(pairs)

    def __iter__(self) -> Iterator[str]:
        for name, _ in self._items:
            yield name

    def __len__(self) -> int:
        return len(self._items)

    def __getitem__(self, key: str) -> SlotValue:
        try:
            return self._items[self._index[key]][1]
        except KeyError as exc:
            raise KeyError(key) from exc

    def __repr__(self) -> str:
        inner = ", ".join(f"{name}={value!r}" for name, value in self._items)
        return f"SlotMap({inner})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, SlotMap):
            return self._items == other._items
        if isinstance(other, Mapping):
            try:
                return self.to_dict() == dict(other)
            except Exception:
                return False
        return NotImplemented

    def items(self) -> tuple[tuple[str, SlotValue], ...]:  # type: ignore[override]
        return self._items

    def keys(self) -> tuple[str, ...]:  # type: ignore[override]
        return tuple(name for name, _ in self._items)

    def values(self) -> tuple[SlotValue, ...]:  # type: ignore[override]
        return tuple(value for _, value in self._items)

    @property
    def slot_names(self) -> tuple[str, ...]:
        return self.keys()

    @property
    def is_empty(self) -> bool:
        return not self._items

    def first(self) -> tuple[str, SlotValue] | None:
        return self._items[0] if self._items else None

    def contains_non_null(self, name: str) -> bool:
        return name in self and self[name] is not None

    def missing(
        self,
        names: Sequence[str],
        *,
        non_null: bool = False,
    ) -> tuple[str, ...]:
        missing_names: list[str] = []
        for name in names:
            if name not in self:
                missing_names.append(name)
            elif non_null and self[name] is None:
                missing_names.append(name)
        return tuple(missing_names)

    def require(self, name: str, *, non_null: bool = False) -> SlotValue:
        if name not in self:
            raise MissingRequiredSlotError(f"Required slot {name!r} is missing.")
        value = self[name]
        if non_null and value is None:
            raise MissingRequiredSlotError(f"Required slot {name!r} is null.")
        return value

    def require_all(
        self,
        names: Sequence[str],
        *,
        non_null: bool = False,
    ) -> "SlotMap":
        missing_names = self.missing(names, non_null=non_null)
        if missing_names:
            joined = ", ".join(repr(name) for name in missing_names)
            raise MissingRequiredSlotError(f"Missing required slots: {joined}.")
        return self

    def validate(self) -> "SlotMap":
        for name in self:
            _validate_slot_name(name)
        return self

    def with_slot(self, name: str, value: SlotValue) -> "SlotMap":
        validated_name = _validate_slot_name(name)
        frozen_value = _freeze_value(value, path=validated_name)

        items = list(self._items)
        if validated_name in self._index:
            items[self._index[validated_name]] = (validated_name, frozen_value)
        else:
            items.append((validated_name, frozen_value))
        return SlotMap(items)

    def merge(
        self,
        other: "SlotMap | Mapping[str, SlotValue]",
        *,
        prefer: str = "right",
    ) -> "SlotMap":
        if prefer not in {"left", "right"}:
            raise ValueError("prefer must be 'left' or 'right'.")

        other_map = other if isinstance(other, SlotMap) else SlotMap(other)

        if prefer == "right":
            result = list(self._items)
            positions = {name: idx for idx, (name, _) in enumerate(result)}
            for name, value in other_map.items():
                if name in positions:
                    result[positions[name]] = (name, value)
                else:
                    positions[name] = len(result)
                    result.append((name, value))
            return SlotMap(result)

        result = list(other_map.items())
        positions = {name: idx for idx, (name, _) in enumerate(result)}
        for name, value in self.items():
            if name in positions:
                result[positions[name]] = (name, value)
            else:
                positions[name] = len(result)
                result.append((name, value))
        return SlotMap(result)

    def __or__(self, other: "SlotMap | Mapping[str, SlotValue]") -> "SlotMap":
        return self.merge(other, prefer="right")

    def without(self, *names: str) -> "SlotMap":
        drop = set(names)
        if not drop:
            return self
        return SlotMap((name, value) for name, value in self._items if name not in drop)

    def subset(self, names: Sequence[str]) -> "SlotMap":
        wanted = set(names)
        return SlotMap((name, value) for name, value in self._items if name in wanted)

    def drop_nulls(self) -> "SlotMap":
        return SlotMap((name, value) for name, value in self._items if value is not None)

    def rename(self, old_name: str, new_name: str) -> "SlotMap":
        if old_name not in self:
            raise MissingRequiredSlotError(f"Cannot rename missing slot {old_name!r}.")
        validated_new = _validate_slot_name(new_name)
        result: list[tuple[str, SlotValue]] = []
        replaced = False
        for name, value in self._items:
            if name == old_name:
                result.append((validated_new, value))
                replaced = True
            elif name != validated_new:
                result.append((name, value))
        if not replaced:
            raise MissingRequiredSlotError(f"Cannot rename missing slot {old_name!r}.")
        return SlotMap(result)

    def to_dict(self) -> dict[str, SlotValue]:
        """Return an ordered shallow dict view of the frozen slot values."""
        return {name: value for name, value in self._items}

    def to_mutable_dict(self) -> dict[str, Any]:
        """Return a deep mutable copy suitable for bridge logic or tests."""
        return {name: _thaw_value(value) for name, value in self._items}

    def to_debug_dict(self) -> dict[str, Any]:
        """
        Return a JSON-friendly representation for debug_info payloads.

        This is intentionally derived data; the canonical SlotMap continues to
        store semantic values, not debug envelopes.
        """
        return {name: _serialize_value(value) for name, value in self._items}


EMPTY_SLOT_MAP = SlotMap.empty()


__all__ = [
    "SlotName",
    "SlotValue",
    "SlotMap",
    "SlotMapError",
    "InvalidSlotNameError",
    "InvalidSlotValueError",
    "MissingRequiredSlotError",
    "EMPTY_SLOT_MAP",
]