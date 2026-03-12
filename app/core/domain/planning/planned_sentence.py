from __future__ import annotations

"""
app/core/domain/planning/planned_sentence.py

Canonical planner-side runtime contract.

`PlannedSentence` is the authoritative sentence-level output of the planner:
it captures *what* sentence is to be said before renderer-facing packaging
(`ConstructionPlan`) and lexical resolution are applied.

This implementation intentionally supports both:

1. The documented canonical contract:
   - construction_id
   - lang_code
   - topic_entity_id
   - focus_role
   - discourse_mode
   - generation_options
   - metadata
   - source_frame_ids
   - priority

2. The repository's current migration needs:
   - an opaque `frame` field is retained for in-process bridging from
     planner output to slot extraction / construction-plan assembly.

Design notes
------------
- Immutable by default (`frozen=True`, `slots=True`).
- Mapping fields are recursively frozen so downstream stages do not mutate
  shared planning state by accident.
- Validation is strict for core contract fields, but intentionally does
  not import the construction registry yet, to avoid circular dependencies
  during the migration batches.
"""

import re
from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import Any
from collections.abc import Iterable, Mapping


_CONSTRUCTION_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_LANG_CODE_RE = re.compile(r"^[a-z]{2,3}(?:-[a-z0-9]{2,8})*$")


def deep_freeze_planning_value(value: Any) -> Any:
    """
    Recursively freeze common mutable containers used in planning payloads.

    Behavior:
    - dict / mapping -> read-only MappingProxyType
    - list / tuple -> tuple
    - set -> frozenset
    - all other objects -> returned as-is

    This function is intentionally conservative: opaque domain objects
    (including dataclass instances) are preserved unchanged.
    """
    if isinstance(value, Mapping):
        frozen = {
            k: deep_freeze_planning_value(v)
            for k, v in value.items()
        }
        return MappingProxyType(frozen)

    if isinstance(value, list):
        return tuple(deep_freeze_planning_value(v) for v in value)

    if isinstance(value, tuple):
        return tuple(deep_freeze_planning_value(v) for v in value)

    if isinstance(value, set):
        return frozenset(deep_freeze_planning_value(v) for v in value)

    return value


def deep_unfreeze_planning_value(value: Any) -> Any:
    """
    Convert frozen planning values back into plain Python containers.

    This is primarily useful for debug serialization and testing.
    """
    if isinstance(value, Mapping):
        return {
            k: deep_unfreeze_planning_value(v)
            for k, v in value.items()
        }

    if isinstance(value, tuple):
        return [deep_unfreeze_planning_value(v) for v in value]

    if isinstance(value, frozenset):
        return [deep_unfreeze_planning_value(v) for v in value]

    return value


def _normalize_required_text(field_name: str, value: Any) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string, got {type(value).__name__}")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


def _normalize_optional_text(field_name: str, value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string or None, got {type(value).__name__}")
    normalized = value.strip()
    return normalized or None


def _normalize_construction_id(value: Any) -> str:
    normalized = _normalize_required_text("construction_id", value)
    if "." in normalized:
        raise ValueError(
            "construction_id must use snake_case runtime IDs, not dotted identifiers"
        )
    if not _CONSTRUCTION_ID_RE.fullmatch(normalized):
        raise ValueError(
            "construction_id must be snake_case, start with a letter, and contain only "
            "lowercase letters, digits, and underscores"
        )
    return normalized


def _normalize_lang_code(value: Any) -> str:
    normalized = _normalize_required_text("lang_code", value).replace("_", "-").lower()
    if not _LANG_CODE_RE.fullmatch(normalized):
        raise ValueError(
            "lang_code must look like an ISO-style language code such as "
            "'en', 'fr', or 'pt-br'"
        )
    return normalized


def _freeze_string_key_mapping(
    field_name: str,
    value: Mapping[str, Any] | None,
) -> Mapping[str, Any]:
    if value is None:
        return MappingProxyType({})

    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be a mapping, got {type(value).__name__}")

    normalized: dict[str, Any] = {}
    for raw_key, raw_val in value.items():
        if not isinstance(raw_key, str):
            raise TypeError(
                f"{field_name} keys must be strings, got {type(raw_key).__name__}"
            )
        key = raw_key.strip()
        if not key:
            raise ValueError(f"{field_name} keys must not be empty")
        normalized[key] = deep_freeze_planning_value(raw_val)

    return MappingProxyType(normalized)


def _extract_frame_id_candidates(frame: Any) -> Iterable[str] | None:
    """
    Heuristic source-frame ID extraction for migration compatibility.

    Supported shapes:
    - mapping with 'source_frame_ids', 'frame_id', or 'id'
    - object attribute 'source_frame_ids', 'frame_id', or 'id'
    """
    if frame is None:
        return None

    if isinstance(frame, Mapping):
        if "source_frame_ids" in frame:
            return frame.get("source_frame_ids")  # type: ignore[return-value]
        if "frame_id" in frame:
            return [frame["frame_id"]]  # type: ignore[index]
        if "id" in frame:
            return [frame["id"]]  # type: ignore[index]
        return None

    for attr_name in ("source_frame_ids", "frame_id", "id"):
        if hasattr(frame, attr_name):
            value = getattr(frame, attr_name)
            if value is not None:
                if attr_name == "source_frame_ids":
                    return value
                return [value]

    return None


def _normalize_source_frame_ids(
    explicit_value: Iterable[str] | None,
    *,
    frame: Any,
) -> tuple[str, ...] | None:
    raw = explicit_value
    if raw is None:
        raw = _extract_frame_id_candidates(frame)

    if raw is None:
        return None

    if isinstance(raw, str):
        raw_iterable: Iterable[Any] = [raw]
    else:
        raw_iterable = raw

    normalized: list[str] = []
    seen: set[str] = set()

    for item in raw_iterable:
        if item is None:
            continue
        if not isinstance(item, str):
            raise TypeError(
                "source_frame_ids must contain strings only; "
                f"got {type(item).__name__}"
            )
        frame_id = item.strip()
        if not frame_id:
            continue
        if frame_id not in seen:
            normalized.append(frame_id)
            seen.add(frame_id)

    return tuple(normalized) if normalized else None


def _normalize_priority(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("priority must be an int or None")
    return value


@dataclass(frozen=True, slots=True)
class PlannedSentence:
    """
    Canonical sentence-level planning decision.

    Required canonical fields
    -------------------------
    construction_id:
        Runtime construction identifier chosen by the planner, e.g.
        "copula_equative_simple" or "topic_comment_eventive".

    lang_code:
        Target language code in normalized lower-case form, e.g. "en",
        "fr", "pt-br".

    Optional planning/discourse fields
    ----------------------------------
    topic_entity_id:
        Entity ID selected as discourse topic for this sentence.

    focus_role:
        Semantic / discourse role that carries sentence focus, e.g.
        "role", "achievement", "event_time_place".

    discourse_mode:
        Optional sentence packaging mode such as "declarative",
        "topic_comment", or another planner-defined label.

    generation_options:
        Planner-side generation hints and defaults. These remain planner /
        plan-level options and must not contain backend-specific AST data.

    metadata:
        Free-form planner metadata, provenance notes, heuristics, or
        migration annotations.

    source_frame_ids:
        IDs of semantic frames that contributed to this sentence. When not
        provided explicitly, a best-effort extraction is attempted from
        `frame`.

    priority:
        Optional planner priority for ordering / tie-breaking.

    Migration compatibility field
    -----------------------------
    frame:
        Opaque normalized semantic frame or planner input object used by
        in-process bridge layers. This is intentionally retained during
        migration even though it is not part of the canonical serialized
        planner contract.
    """

    construction_id: str
    lang_code: str

    frame: Any | None = None
    topic_entity_id: str | None = None
    focus_role: str | None = None
    discourse_mode: str | None = None

    generation_options: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    source_frame_ids: tuple[str, ...] | None = None
    priority: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "construction_id", _normalize_construction_id(self.construction_id))
        object.__setattr__(self, "lang_code", _normalize_lang_code(self.lang_code))

        # Freeze frame opportunistically when it is a common mutable
        # container. Opaque domain objects are preserved unchanged.
        object.__setattr__(self, "frame", deep_freeze_planning_value(self.frame))

        object.__setattr__(
            self,
            "topic_entity_id",
            _normalize_optional_text("topic_entity_id", self.topic_entity_id),
        )
        object.__setattr__(
            self,
            "focus_role",
            _normalize_optional_text("focus_role", self.focus_role),
        )
        object.__setattr__(
            self,
            "discourse_mode",
            _normalize_optional_text("discourse_mode", self.discourse_mode),
        )

        object.__setattr__(
            self,
            "generation_options",
            _freeze_string_key_mapping("generation_options", self.generation_options),
        )
        object.__setattr__(
            self,
            "metadata",
            _freeze_string_key_mapping("metadata", self.metadata),
        )
        object.__setattr__(
            self,
            "source_frame_ids",
            _normalize_source_frame_ids(self.source_frame_ids, frame=self.frame),
        )
        object.__setattr__(self, "priority", _normalize_priority(self.priority))

    @property
    def has_topic(self) -> bool:
        return self.topic_entity_id is not None

    @property
    def has_focus(self) -> bool:
        return self.focus_role is not None

    @property
    def primary_source_frame_id(self) -> str | None:
        if not self.source_frame_ids:
            return None
        return self.source_frame_ids[0]

    def with_updates(self, **changes: Any) -> "PlannedSentence":
        """
        Return a new instance with selected fields replaced.

        Example:
            updated = sent.with_updates(
                focus_role="achievement",
                metadata={**sent.metadata, "planner": "bio_v2"},
            )
        """
        return replace(self, **changes)

    def to_dict(self, *, include_frame: bool = False) -> dict[str, Any]:
        """
        Serialize to a plain-Python dict suitable for logging, tests, or
        response mapping.

        The opaque `frame` field is excluded by default because it is an
        in-process compatibility carrier and may not be safely serializable.
        """
        data: dict[str, Any] = {
            "construction_id": self.construction_id,
            "lang_code": self.lang_code,
            "topic_entity_id": self.topic_entity_id,
            "focus_role": self.focus_role,
            "discourse_mode": self.discourse_mode,
            "generation_options": deep_unfreeze_planning_value(self.generation_options),
            "metadata": deep_unfreeze_planning_value(self.metadata),
            "source_frame_ids": list(self.source_frame_ids) if self.source_frame_ids else None,
            "priority": self.priority,
        }

        if include_frame:
            data["frame"] = deep_unfreeze_planning_value(self.frame)

        return data

    @classmethod
    def for_frame(
        cls,
        frame: Any,
        *,
        construction_id: str,
        lang_code: str,
        topic_entity_id: str | None = None,
        focus_role: str | None = None,
        discourse_mode: str | None = None,
        generation_options: Mapping[str, Any] | None = None,
        metadata: Mapping[str, Any] | None = None,
        source_frame_ids: Iterable[str] | None = None,
        priority: int | None = None,
    ) -> "PlannedSentence":
        """
        Convenience constructor used by planner implementations that are
        starting from a normalized semantic frame.
        """
        return cls(
            construction_id=construction_id,
            lang_code=lang_code,
            frame=frame,
            topic_entity_id=topic_entity_id,
            focus_role=focus_role,
            discourse_mode=discourse_mode,
            generation_options=generation_options or {},
            metadata=metadata or {},
            source_frame_ids=tuple(source_frame_ids) if source_frame_ids is not None else None,
            priority=priority,
        )


__all__ = [
    "PlannedSentence",
    "deep_freeze_planning_value",
    "deep_unfreeze_planning_value",
]