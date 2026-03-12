# app/core/bridges/frame_to_slots.py
"""
Bridge normalized semantic frames into canonical runtime slot maps.

This module is the planner-side / construction-side bridge that:

1. reads a normalized frame-like object,
2. inspects the target construction_id,
3. extracts semantic role values,
4. normalizes them into canonical, backend-agnostic slot names,
5. returns a JSON-friendly SlotMap (plain dict[str, Any]).

Design constraints
------------------
- Slot names are semantic or constructional, never backend-internal.
- Plan-level fields (construction_id, lang_code, generation_options, etc.)
  MUST NOT appear inside the slot_map.
- This bridge classifies values (entity vs lexeme vs time vs location), but
  it does NOT perform lexical lookup / lexicon ID assignment. That belongs to
  the lexical-resolution layer.

The implementation is intentionally tolerant of current repository shapes:
- plain dict payloads,
- Pydantic models,
- dataclasses,
- loose semantic frame objects with attributes,
- legacy "bio"/"event" payloads,
- richer semantic objects from app.core.domain.semantics.types.
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
import re
from typing import Any, Callable, Dict, Iterable, Mapping, Optional, Sequence

try:
    from pydantic import BaseModel
except Exception:  # pragma: no cover
    BaseModel = None  # type: ignore[assignment]


JSONScalar = None | bool | int | float | str
JSONValue = JSONScalar | list["JSONValue"] | dict[str, "JSONValue"]
SlotMap = dict[str, Any]


_RESERVED_PLAN_FIELDS = {
    "construction_id",
    "lang_code",
    "generation_options",
    "topic_entity_id",
    "focus_role",
    "lexical_bindings",
    "provenance",
    "renderer_backend",
    "debug_info",
    "metadata",
    "slot_map_version",
    "frame_ref",
    "discourse",
    "generation",
    "lexical_requirements",
}

_SLOT_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_YEAR_RE = re.compile(r"^\d{4}$")
_DATE_RE = re.compile(r"^(?P<y>\d{4})-(?P<m>\d{2})-(?P<d>\d{2})$")
_QID_RE = re.compile(r"^Q\d+$", re.IGNORECASE)


class FrameToSlotsError(ValueError):
    """Base error for frame-to-slot mapping failures."""


class UnsupportedConstructionError(FrameToSlotsError):
    """Raised when a construction_id cannot be handled."""


class MissingRequiredRoleError(FrameToSlotsError):
    """Raised when a construction-required semantic role is missing."""


class InvalidSlotMapError(FrameToSlotsError):
    """Raised when a produced slot map violates canonical slot-map rules."""


def frame_to_slots(
    frame: Any,
    *,
    construction_id: str,
) -> SlotMap:
    """
    Convenience functional entrypoint.

    Args:
        frame:
            Frame-like semantic object (dict, dataclass, Pydantic model, or
            attribute-bearing object).
        construction_id:
            Canonical construction identifier selected by the planner.

    Returns:
        Canonical slot map for the construction.
    """
    return FrameToSlotsBridge().build_slot_map(
        frame,
        construction_id=construction_id,
    )


class FrameToSlotsBridge:
    """
    Canonical frame-to-slot bridge.

    The bridge is deterministic and intentionally side-effect free.
    """

    def __init__(
        self,
        custom_handlers: Optional[Mapping[str, Callable[[Mapping[str, Any]], SlotMap]]] = None,
    ) -> None:
        self._handlers: dict[str, Callable[[Mapping[str, Any]], SlotMap]] = {
            "copula_equative_simple": self._build_copula_equative_simple,
            "copula_equative_classification": self._build_copula_equative_classification,
            "copula_attributive_np": self._build_copula_attributive_np,
            "copula_attributive_adj": self._build_copula_attributive_adj,
            "copula_locative": self._build_copula_locative,
            "copula_existential": self._build_copula_existential,
            "possession_have": self._build_possession_have,
            "possession_existential": self._build_possession_existential,
            "intransitive_event": self._build_intransitive_event,
            "transitive_event": self._build_transitive_event,
            "ditransitive_event": self._build_ditransitive_event,
            "passive_event": self._build_passive_event,
            "topic_comment_copular": self._build_topic_comment_copular,
            "topic_comment_eventive": self._build_topic_comment_eventive,
            "coordination_clauses": self._build_coordination_clauses,
            "relative_clause_subject_gap": self._build_relative_clause_subject_gap,
            "relative_clause_object_gap": self._build_relative_clause_object_gap,
        }
        if custom_handlers:
            for raw_id, handler in custom_handlers.items():
                self._handlers[_normalize_identifier(raw_id)] = handler

    def supports(self, construction_id: str) -> bool:
        """Return True if the bridge has an explicit handler for this construction."""
        return _normalize_identifier(construction_id) in self._handlers

    def build_slot_map(
        self,
        frame: Any,
        *,
        construction_id: str,
    ) -> SlotMap:
        """
        Build a canonical slot_map from a normalized frame and target construction.

        Unknown constructions fall back to a generic semantic-role extractor rather
        than failing immediately, but only if at least one meaningful slot can be
        produced.
        """
        cid = _normalize_identifier(construction_id)
        frame_map = _frame_to_mapping(frame)

        handler = self._handlers.get(cid)
        if handler is None:
            slot_map = self._build_generic(frame_map, construction_id=cid)
        else:
            slot_map = handler(frame_map)

        return _finalize_slot_map(slot_map)

    __call__ = build_slot_map

    # ------------------------------------------------------------------ #
    # Construction handlers                                              #
    # ------------------------------------------------------------------ #

    def _build_copula_equative_simple(self, frame: Mapping[str, Any]) -> SlotMap:
        subject = _require(_extract_subject(frame), role="subject")
        profession = _extract_profession(frame)
        nationality = _extract_nationality(frame)
        predicate_nominal = _extract_predicate_nominal(
            frame,
            profession=profession,
            nationality=nationality,
        )

        if predicate_nominal is None:
            raise MissingRequiredRoleError(
                "copula_equative_simple requires subject and predicate_nominal-compatible content."
            )

        out: SlotMap = {
            "subject": subject,
            "predicate_nominal": predicate_nominal,
        }
        if profession is not None:
            out["profession"] = profession
        if nationality is not None:
            out["nationality"] = nationality
        return _maybe_add_common_modifiers(frame, out)

    def _build_copula_equative_classification(self, frame: Mapping[str, Any]) -> SlotMap:
        subject = _require(_extract_subject(frame), role="subject")
        profession = _extract_profession(frame)
        nationality = _extract_nationality(frame)

        out: SlotMap = {"subject": subject}
        if profession is not None:
            out["profession"] = profession
        if nationality is not None:
            out["nationality"] = nationality

        predicate_nominal = _extract_predicate_nominal(
            frame,
            profession=profession,
            nationality=nationality,
        )
        if predicate_nominal is not None:
            out["predicate_nominal"] = predicate_nominal

        if len(out) == 1:
            raise MissingRequiredRoleError(
                "copula_equative_classification requires subject plus profession, nationality, or predicate_nominal."
            )
        return _maybe_add_common_modifiers(frame, out)

    def _build_copula_attributive_np(self, frame: Mapping[str, Any]) -> SlotMap:
        subject = _require(_extract_subject(frame), role="subject")
        predicate_nominal = _require(
            _extract_predicate_nominal(frame),
            role="predicate_nominal",
        )
        out: SlotMap = {
            "subject": subject,
            "predicate_nominal": predicate_nominal,
        }
        return _maybe_add_common_modifiers(frame, out)

    def _build_copula_attributive_adj(self, frame: Mapping[str, Any]) -> SlotMap:
        subject = _require(_extract_subject(frame), role="subject")
        predicate_adjective = _require(
            _extract_predicate_adjective(frame),
            role="predicate_adjective",
        )
        out: SlotMap = {
            "subject": subject,
            "predicate_adjective": predicate_adjective,
        }
        return _maybe_add_common_modifiers(frame, out)

    def _build_copula_locative(self, frame: Mapping[str, Any]) -> SlotMap:
        subject = _require(_extract_subject(frame), role="subject")
        location = _require(_extract_location(frame), role="location")
        out: SlotMap = {
            "subject": subject,
            "location": location,
        }
        return _maybe_add_common_modifiers(frame, out)

    def _build_copula_existential(self, frame: Mapping[str, Any]) -> SlotMap:
        existent = (
            _extract_explicit_role(frame, "existent")
            or _extract_object(frame)
            or _extract_subject(frame)
        )
        existent = _require(existent, role="existent")

        out: SlotMap = {"existent": existent}
        location = _extract_location(frame)
        if location is not None:
            out["location"] = location
        return _maybe_add_common_modifiers(frame, out)

    def _build_possession_have(self, frame: Mapping[str, Any]) -> SlotMap:
        possessor = (
            _extract_explicit_role(frame, "possessor")
            or _extract_subject(frame)
            or _extract_owner(frame)
        )
        possessed = (
            _extract_explicit_role(frame, "possessed")
            or _extract_object(frame)
            or _extract_theme(frame)
        )

        out: SlotMap = {
            "possessor": _require(possessor, role="possessor"),
            "possessed": _require(possessed, role="possessed"),
        }

        quantity = _extract_quantity(frame)
        if quantity is not None:
            out["quantity"] = quantity
        return _maybe_add_common_modifiers(frame, out)

    def _build_possession_existential(self, frame: Mapping[str, Any]) -> SlotMap:
        out = self._build_possession_have(frame)
        location = _extract_location(frame)
        if location is not None:
            out["location"] = location
        return _maybe_add_common_modifiers(frame, out)

    def _build_intransitive_event(self, frame: Mapping[str, Any]) -> SlotMap:
        subject = _require(_extract_subject(frame), role="subject")
        predicate = _require(_extract_event_predicate(frame), role="predicate")

        out: SlotMap = {
            "subject": subject,
            "predicate": predicate,
        }
        return _maybe_add_common_modifiers(frame, out)

    def _build_transitive_event(self, frame: Mapping[str, Any]) -> SlotMap:
        subject = _require(
            _extract_explicit_role(frame, "agent")
            or _extract_subject(frame),
            role="subject",
        )
        obj = _require(
            _extract_explicit_role(frame, "object")
            or _extract_patient(frame)
            or _extract_theme(frame)
            or _extract_object(frame),
            role="object",
        )
        predicate = _require(_extract_event_predicate(frame), role="predicate")

        out: SlotMap = {
            "subject": subject,
            "object": obj,
            "predicate": predicate,
        }
        return _maybe_add_common_modifiers(frame, out)

    def _build_ditransitive_event(self, frame: Mapping[str, Any]) -> SlotMap:
        subject = _require(
            _extract_explicit_role(frame, "agent")
            or _extract_subject(frame),
            role="subject",
        )
        theme = _require(
            _extract_theme(frame) or _extract_object(frame),
            role="theme",
        )
        recipient = _require(
            _extract_recipient(frame),
            role="recipient",
        )
        predicate = _require(_extract_event_predicate(frame), role="predicate")

        out: SlotMap = {
            "subject": subject,
            "theme": theme,
            "recipient": recipient,
            "predicate": predicate,
        }
        return _maybe_add_common_modifiers(frame, out)

    def _build_passive_event(self, frame: Mapping[str, Any]) -> SlotMap:
        patient = _require(
            _extract_patient(frame) or _extract_object(frame) or _extract_theme(frame),
            role="patient",
        )
        predicate = _require(_extract_event_predicate(frame), role="predicate")

        out: SlotMap = {
            "patient": patient,
            "predicate": predicate,
        }
        agent = _extract_explicit_role(frame, "agent") or _extract_subject(frame)
        if agent is not None:
            out["agent"] = agent
        return _maybe_add_common_modifiers(frame, out)

    def _build_topic_comment_copular(self, frame: Mapping[str, Any]) -> SlotMap:
        topic = _require(_extract_topic(frame) or _extract_subject(frame), role="topic")
        subject = _extract_subject(frame) or topic

        profession = _extract_profession(frame)
        nationality = _extract_nationality(frame)
        predicate_nominal = _require(
            _extract_predicate_nominal(frame, profession=profession, nationality=nationality),
            role="predicate_nominal",
        )

        out: SlotMap = {
            "topic": topic,
            "subject": subject,
            "predicate_nominal": predicate_nominal,
        }
        if profession is not None:
            out["profession"] = profession
        if nationality is not None:
            out["nationality"] = nationality
        return _maybe_add_common_modifiers(frame, out)

    def _build_topic_comment_eventive(self, frame: Mapping[str, Any]) -> SlotMap:
        topic = _require(_extract_topic(frame) or _extract_subject(frame), role="topic")
        predicate = _require(_extract_event_predicate(frame), role="predicate")

        out: SlotMap = {
            "topic": topic,
            "predicate": predicate,
        }

        subject = _extract_subject(frame)
        if subject is not None:
            out["subject"] = subject

        obj = _extract_object(frame)
        if obj is not None:
            out["object"] = obj

        return _maybe_add_common_modifiers(frame, out)

    def _build_coordination_clauses(self, frame: Mapping[str, Any]) -> SlotMap:
        conjuncts_raw = (
            _first_non_empty_value(
                _nested_get(frame, ("conjuncts",)),
                _nested_get(frame, ("clauses",)),
                _nested_get(frame, ("items",)),
                _nested_get(frame, ("properties", "conjuncts")),
                _nested_get(frame, ("properties", "clauses")),
            )
        )
        conjuncts: list[JSONValue] = []

        if isinstance(conjuncts_raw, Sequence) and not isinstance(conjuncts_raw, (str, bytes, bytearray)):
            for item in conjuncts_raw:
                conjuncts.append(_to_json_value(item))

        if not conjuncts:
            raise MissingRequiredRoleError(
                "coordination_clauses requires at least one conjunct/clauses/items sequence."
            )

        return {"conjuncts": conjuncts}

    def _build_relative_clause_subject_gap(self, frame: Mapping[str, Any]) -> SlotMap:
        head = _require(
            _extract_explicit_role(frame, "head")
            or _extract_subject(frame)
            or _extract_object(frame),
            role="head",
        )
        predicate = _require(_extract_event_predicate(frame), role="predicate")

        out: SlotMap = {
            "head": head,
            "predicate": predicate,
        }
        obj = _extract_object(frame)
        if obj is not None:
            out["object"] = obj
        return _maybe_add_common_modifiers(frame, out)

    def _build_relative_clause_object_gap(self, frame: Mapping[str, Any]) -> SlotMap:
        head = _require(
            _extract_explicit_role(frame, "head")
            or _extract_object(frame)
            or _extract_patient(frame)
            or _extract_theme(frame),
            role="head",
        )
        predicate = _require(_extract_event_predicate(frame), role="predicate")
        subject = _require(_extract_subject(frame), role="subject")

        out: SlotMap = {
            "head": head,
            "subject": subject,
            "predicate": predicate,
        }
        return _maybe_add_common_modifiers(frame, out)

    def _build_generic(
        self,
        frame: Mapping[str, Any],
        *,
        construction_id: str,
    ) -> SlotMap:
        """
        Generic semantic-role extraction fallback.

        This is intentionally conservative: if nothing meaningful can be
        recovered, we raise UnsupportedConstructionError rather than emit an
        empty or misleading slot map.
        """
        out: SlotMap = {}

        role_extractors: list[tuple[str, Callable[[Mapping[str, Any]], Any]]] = [
            ("topic", _extract_topic),
            ("subject", _extract_subject),
            ("predicate_nominal", _extract_predicate_nominal),
            ("predicate_adjective", _extract_predicate_adjective),
            ("predicate", _extract_event_predicate),
            ("object", _extract_object),
            ("agent", _extract_agent),
            ("patient", _extract_patient),
            ("recipient", _extract_recipient),
            ("theme", _extract_theme),
            ("location", _extract_location),
            ("time", _extract_time),
            ("quantity", _extract_quantity),
            ("profession", _extract_profession),
            ("nationality", _extract_nationality),
            ("comment", _extract_comment),
        ]

        for slot_name, extractor in role_extractors:
            value = extractor(frame)
            if value is not None:
                out[slot_name] = value

        out = _maybe_add_common_modifiers(frame, out)

        if not out:
            raise UnsupportedConstructionError(
                f"No frame-to-slot mapping rule produced content for {construction_id!r}."
            )

        return out


# ---------------------------------------------------------------------- #
# Frame normalization                                                    #
# ---------------------------------------------------------------------- #


def _frame_to_mapping(frame: Any) -> dict[str, Any]:
    """
    Convert any supported frame-like object to a plain dict.

    Supported:
    - dict / Mapping
    - Pydantic model
    - dataclass instance
    - regular objects with attributes
    """
    plain = _to_plain(frame)
    if not isinstance(plain, Mapping):
        raise FrameToSlotsError(
            f"Frame must be mapping-like after normalization; got {type(plain).__name__}."
        )
    return {str(k): v for k, v in plain.items()}


def _to_plain(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int, float)):
        return value

    if isinstance(value, Mapping):
        return {str(k): _to_plain(v) for k, v in value.items()}

    if isinstance(value, (list, tuple, set)):
        return [_to_plain(v) for v in value]

    if BaseModel is not None and isinstance(value, BaseModel):
        return _to_plain(value.model_dump(exclude_none=True))

    if is_dataclass(value) and not isinstance(value, type):
        return _to_plain(asdict(value))

    if hasattr(value, "__dict__"):
        data = {
            k: getattr(value, k)
            for k in dir(value)
            if not k.startswith("_")
            and not callable(getattr(value, k, None))
        }
        return _to_plain(data)

    return value


def _to_json_value(value: Any) -> JSONValue:
    plain = _to_plain(value)

    if plain is None or isinstance(plain, (str, bool, int, float)):
        return plain

    if isinstance(plain, list):
        return [_to_json_value(v) for v in plain]

    if isinstance(plain, Mapping):
        return {str(k): _to_json_value(v) for k, v in plain.items()}

    return str(plain)


# ---------------------------------------------------------------------- #
# Generic extraction helpers                                             #
# ---------------------------------------------------------------------- #


def _normalize_identifier(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    if not text:
        raise FrameToSlotsError("Identifier must not be empty.")
    return text


def _normalize_slot_name(name: str) -> str:
    normalized = _normalize_identifier(name)
    if normalized in _RESERVED_PLAN_FIELDS:
        raise InvalidSlotMapError(
            f"Reserved plan-level field {normalized!r} must not appear as a slot key."
        )
    if not _SLOT_NAME_RE.fullmatch(normalized):
        raise InvalidSlotMapError(f"Invalid slot key {name!r}.")
    return normalized


def _nested_get(data: Mapping[str, Any], path: Sequence[str]) -> Any:
    current: Any = data
    for key in path:
        if not isinstance(current, Mapping) or key not in current:
            return None
        current = current[key]
    return current


def _first_non_empty_value(*values: Any) -> Any:
    for value in values:
        if _has_meaningful_value(value):
            return value
    return None


def _has_meaningful_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, Mapping):
        return any(_has_meaningful_value(v) for v in value.values())
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return any(_has_meaningful_value(v) for v in value)
    return True


def _strip_str(value: Any) -> Optional[str]:
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return None


def _merge_dicts(*mappings: Optional[Mapping[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for mapping in mappings:
        if not isinstance(mapping, Mapping):
            continue
        for key, value in mapping.items():
            out[str(key)] = value
    return out


def _search_spaces(frame: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    spaces: list[Mapping[str, Any]] = [frame]

    for key in ("properties", "attributes", "extra", "meta"):
        candidate = frame.get(key)
        if isinstance(candidate, Mapping):
            spaces.append(candidate)

    event = _event_mapping(frame)
    if event is not None:
        spaces.append(event)
        for key in ("properties", "extra"):
            candidate = event.get(key)
            if isinstance(candidate, Mapping):
                spaces.append(candidate)

    return spaces


def _find_first_by_paths(frame: Mapping[str, Any], paths: Sequence[Sequence[str]]) -> Any:
    for space in _search_spaces(frame):
        for path in paths:
            value = _nested_get(space, path)
            if _has_meaningful_value(value):
                return value
    return None


def _require(value: Any, *, role: str) -> Any:
    if value is None:
        raise MissingRequiredRoleError(f"Missing required semantic role {role!r}.")
    return value


def _event_mapping(frame: Mapping[str, Any]) -> Optional[Mapping[str, Any]]:
    candidates = [
        _nested_get(frame, ("main_event",)),
        _nested_get(frame, ("event",)),
        _nested_get(frame, ("properties", "main_event")),
        _nested_get(frame, ("properties", "event")),
    ]
    for candidate in candidates:
        if isinstance(candidate, Mapping):
            return candidate

    if "event_type" in frame or "participants" in frame:
        return frame
    return None


def _participants_mapping(frame: Mapping[str, Any]) -> Mapping[str, Any]:
    event = _event_mapping(frame)
    if isinstance(event, Mapping):
        participants = event.get("participants")
        if isinstance(participants, Mapping):
            return participants
    participants = frame.get("participants")
    if isinstance(participants, Mapping):
        return participants
    return {}


# ---------------------------------------------------------------------- #
# Role extractors                                                        #
# ---------------------------------------------------------------------- #


def _extract_explicit_role(frame: Mapping[str, Any], role_name: str) -> Any:
    role_name = _normalize_identifier(role_name)
    participants = _participants_mapping(frame)
    if role_name in participants:
        value = _normalize_role_value(role_name, participants[role_name])
        if value is not None:
            return value

    paths = [
        (role_name,),
        ("properties", role_name),
        ("attributes", role_name),
    ]
    raw = _find_first_by_paths(frame, paths)
    return _normalize_role_value(role_name, raw)


def _extract_topic(frame: Mapping[str, Any]) -> Any:
    raw = _find_first_by_paths(
        frame,
        [
            ("topic",),
            ("properties", "topic"),
            ("main_entity",),
            ("subject",),
        ],
    )
    return _normalize_entity_ref(raw)

def _extract_comment(frame: Mapping[str, Any]) -> Any:
    raw = _find_first_by_paths(
        frame,
        [
            ("comment",),
            ("properties", "comment"),
        ],
    )
    if raw is None:
        return None
    return _to_json_value(raw)

def _extract_subject(frame: Mapping[str, Any]) -> Any:
    participants = _participants_mapping(frame)
    raw = _first_non_empty_value(
        participants.get("subject"),
        participants.get("agent"),
        _find_first_by_paths(
            frame,
            [
                ("subject",),
                ("main_entity",),
                ("entity",),
                ("owner",),
            ],
        ),
    )
    return _normalize_entity_ref(raw)

def _extract_agent(frame: Mapping[str, Any]) -> Any:
    participants = _participants_mapping(frame)
    raw = _first_non_empty_value(
        participants.get("agent"),
        participants.get("subject"),
        _find_first_by_paths(frame, [("agent",), ("properties", "agent")]),
    )
    return _normalize_entity_ref(raw)

def _extract_object(frame: Mapping[str, Any]) -> Any:
    participants = _participants_mapping(frame)
    raw = _first_non_empty_value(
        participants.get("object"),
        participants.get("patient"),
        participants.get("theme"),
        _find_first_by_paths(
            frame,
            [
                ("object",),
                ("event_object",),
                ("main_object",),
                ("properties", "object"),
            ],
        ),
    )
    return _normalize_entity_ref(raw)

def _extract_patient(frame: Mapping[str, Any]) -> Any:
    participants = _participants_mapping(frame)
    raw = _first_non_empty_value(
        participants.get("patient"),
        _find_first_by_paths(frame, [("patient",), ("properties", "patient")]),
    )
    return _normalize_entity_ref(raw)

def _extract_theme(frame: Mapping[str, Any]) -> Any:
    participants = _participants_mapping(frame)
    raw = _first_non_empty_value(
        participants.get("theme"),
        _find_first_by_paths(frame, [("theme",), ("properties", "theme")]),
    )
    return _normalize_entity_ref(raw)

def _extract_recipient(frame: Mapping[str, Any]) -> Any:
    participants = _participants_mapping(frame)
    raw = _first_non_empty_value(
        participants.get("recipient"),
        participants.get("beneficiary"),
        _find_first_by_paths(
            frame,
            [("recipient",), ("beneficiary",), ("properties", "recipient")],
        ),
    )
    return _normalize_entity_ref(raw)

def _extract_owner(frame: Mapping[str, Any]) -> Any:
    raw = _find_first_by_paths(
        frame,
        [
            ("owner",),
            ("possessor",),
            ("properties", "owner"),
            ("properties", "possessor"),
        ],
    )
    return _normalize_entity_ref(raw)

def _extract_location(frame: Mapping[str, Any]) -> Any:
    event = _event_mapping(frame)
    raw = _first_non_empty_value(
        event.get("location") if isinstance(event, Mapping) else None,
        _find_first_by_paths(
            frame,
            [
                ("location",),
                ("place",),
                ("properties", "location"),
                ("properties", "place"),
            ],
        ),
    )
    return _normalize_location_ref(raw)

def _extract_time(frame: Mapping[str, Any]) -> Any:
    event = _event_mapping(frame)
    raw = _first_non_empty_value(
        event.get("time") if isinstance(event, Mapping) else None,
        event.get("date") if isinstance(event, Mapping) else None,
        _find_first_by_paths(
            frame,
            [
                ("time",),
                ("date",),
                ("when",),
                ("properties", "time"),
                ("properties", "date"),
            ],
        ),
    )
    return _normalize_time_value(raw)

def _extract_quantity(frame: Mapping[str, Any]) -> Any:
    raw = _find_first_by_paths(
        frame,
        [
            ("quantity",),
            ("count",),
            ("amount",),
            ("properties", "quantity"),
            ("properties", "count"),
        ],
    )
    return _normalize_quantity_value(raw)

def _extract_profession(frame: Mapping[str, Any]) -> Any:
    raw = _first_non_empty_value(
        _find_first_by_paths(
            frame,
            [
                ("profession",),
                ("profession_lemma",),
                ("occupation",),
                ("occupation_lemma",),
                ("properties", "profession"),
                ("properties", "occupation"),
                ("subject", "profession"),
            ],
        ),
        _extract_first_string_list_item(
            _find_first_by_paths(
                frame,
                [
                    ("primary_profession_lemmas",),
                    ("profession_lemmas",),
                    ("occupation_lemmas",),
                    ("properties", "primary_profession_lemmas"),
                ],
            )
        ),
    )
    return _normalize_lexeme_ref(raw, default_pos="NOUN")

def _extract_nationality(frame: Mapping[str, Any]) -> Any:
    raw = _first_non_empty_value(
        _find_first_by_paths(
            frame,
            [
                ("nationality",),
                ("nationality_lemma",),
                ("properties", "nationality"),
                ("subject", "nationality"),
            ],
        ),
        _extract_first_string_list_item(
            _find_first_by_paths(
                frame,
                [
                    ("nationality_lemmas",),
                    ("properties", "nationality_lemmas"),
                ],
            )
        ),
    )
    return _normalize_lexeme_ref(raw, default_pos="ADJ")

def _extract_predicate_nominal(
    frame: Mapping[str, Any],
    *,
    profession: Any = None,
    nationality: Any = None,
) -> Any:
    explicit = _find_first_by_paths(
        frame,
        [
            ("predicate_nominal",),
            ("class",),
            ("class_lemma",),
            ("type_lemma",),
            ("kind_lemma",),
            ("role_lemma",),
            ("properties", "predicate_nominal"),
            ("properties", "class"),
            ("properties", "class_lemma"),
        ],
    )
    normalized_explicit = _normalize_lexeme_ref(explicit, default_pos="NOUN")
    if normalized_explicit is not None:
        return normalized_explicit

    if profession is not None and nationality is not None:
        return {
            "role": "profession_plus_nationality",
            "profession": profession,
            "nationality": nationality,
        }

    if profession is not None:
        return profession

    if nationality is not None:
        return nationality

    return None

def _extract_predicate_adjective(frame: Mapping[str, Any]) -> Any:
    raw = _find_first_by_paths(
        frame,
        [
            ("predicate_adjective",),
            ("adjective",),
            ("adjective_lemma",),
            ("quality",),
            ("quality_lemma",),
            ("properties", "predicate_adjective"),
            ("properties", "adjective"),
        ],
    )
    return _normalize_lexeme_ref(raw, default_pos="ADJ")

def _extract_event_predicate(frame: Mapping[str, Any]) -> Any:
    event = _event_mapping(frame)
    event_type = None
    if isinstance(event, Mapping):
        event_type = _strip_str(event.get("event_type"))

    explicit = _find_first_by_paths(
        frame,
        [
            ("verb_lemma",),
            ("predicate",),
            ("predicate_lemma",),
            ("action_lemma",),
            ("properties", "verb_lemma"),
            ("properties", "predicate_lemma"),
        ],
    )
    lex = _normalize_lexeme_ref(explicit, default_pos="VERB")
    if lex is not None:
        if event_type:
            lex = dict(lex)
            lex.setdefault("event_type", event_type)
        return lex

    if event_type:
        return {
            "lemma": event_type,
            "pos": "VERB",
            "source": "frame",
            "event_type": event_type,
        }

    return None


# ---------------------------------------------------------------------- #
# Value normalizers                                                      #
# ---------------------------------------------------------------------- #


def _normalize_role_value(role_name: str, raw: Any) -> Any:
    role_name = _normalize_identifier(role_name)

    if role_name in {"subject", "object", "agent", "patient", "recipient", "theme", "topic", "possessor", "possessed", "existent", "head"}:
        return _normalize_entity_ref(raw)
    if role_name in {"profession", "nationality", "predicate_nominal"}:
        return _normalize_lexeme_ref(raw, default_pos="NOUN")
    if role_name == "predicate_adjective":
        return _normalize_lexeme_ref(raw, default_pos="ADJ")
    if role_name == "location":
        return _normalize_location_ref(raw)
    if role_name == "time":
        return _normalize_time_value(raw)
    if role_name == "quantity":
        return _normalize_quantity_value(raw)
    if role_name in {"predicate", "verb"}:
        return _normalize_lexeme_ref(raw, default_pos="VERB")
    return _to_json_value(raw) if raw is not None else None


def _normalize_entity_ref(raw: Any, *, entity_type_hint: Optional[str] = None) -> Optional[dict[str, JSONValue]]:
    if raw is None:
        return None

    if isinstance(raw, str):
        label = raw.strip()
        if not label:
            return None
        out = {"label": label}
        if entity_type_hint:
            out["entity_type"] = entity_type_hint
        return out

    data = _to_plain(raw)
    if not isinstance(data, Mapping):
        text = str(data).strip()
        return {"label": text} if text else None

    label = _first_non_empty_value(
        _strip_str(data.get("label")),
        _strip_str(data.get("name")),
        _strip_str(data.get("title")),
    )

    qid = _first_non_empty_value(
        _strip_str(data.get("qid")),
        _strip_str(data.get("wikidata_qid")),
    )
    entity_id = _first_non_empty_value(
        _strip_str(data.get("entity_id")),
        _strip_str(data.get("id")),
        _strip_str(data.get("target_id")),
        qid,
    )

    entity_type = _first_non_empty_value(
        _strip_str(data.get("entity_type")),
        _strip_str(data.get("kind")),
        _strip_str(data.get("type")),
        entity_type_hint,
    )

    features = _merge_dicts(
        data.get("features") if isinstance(data.get("features"), Mapping) else None,
        {
            k: data.get(k)
            for k in ("gender", "human", "person", "number")
            if data.get(k) is not None
        },
    )

    extra = {
        str(k): _to_json_value(v)
        for k, v in data.items()
        if k not in {
            "label",
            "name",
            "title",
            "qid",
            "wikidata_qid",
            "entity_id",
            "id",
            "target_id",
            "entity_type",
            "kind",
            "type",
            "features",
            "gender",
            "human",
            "person",
            "number",
        }
    }

    out: dict[str, JSONValue] = {}
    if label is not None:
        out["label"] = label
    if entity_id is not None:
        out["entity_id"] = entity_id
    if qid is not None:
        out["qid"] = qid
    if entity_type is not None:
        out["entity_type"] = entity_type
    if features:
        out["features"] = _to_json_value(features)
    if extra:
        out["extra"] = _to_json_value(extra)

    if not out:
        return None
    if "label" not in out and "entity_id" not in out and "qid" not in out:
        return None
    return out


def _normalize_location_ref(raw: Any) -> Optional[dict[str, JSONValue]]:
    entity = _normalize_entity_ref(raw, entity_type_hint="place")
    if entity is None:
        return None

    data = _to_plain(raw)
    if isinstance(data, Mapping):
        country_code = _first_non_empty_value(
            _strip_str(data.get("country_code")),
            _strip_str(data.get("countryCode")),
            _strip_str(data.get("iso_country_code")),
            _strip_str(data.get("iso_3166_1_alpha2")),
        )
        location_type = _first_non_empty_value(
            _strip_str(data.get("location_type")),
            _strip_str(data.get("kind")),
        )
        if country_code is not None:
            entity["country_code"] = country_code.upper()
        if location_type is not None:
            entity["location_type"] = location_type
    return entity


def _normalize_lexeme_ref(raw: Any, *, default_pos: Optional[str] = None) -> Optional[dict[str, JSONValue]]:
    if raw is None:
        return None

    if isinstance(raw, str):
        lemma = raw.strip()
        if not lemma:
            return None
        out: dict[str, JSONValue] = {"lemma": lemma, "source": "frame"}
        if default_pos is not None:
            out["pos"] = default_pos
        return out

    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes, bytearray)):
        first = _extract_first_string_list_item(raw)
        return _normalize_lexeme_ref(first, default_pos=default_pos)

    data = _to_plain(raw)
    if not isinstance(data, Mapping):
        text = str(data).strip()
        return {"lemma": text, "pos": default_pos or "X", "source": "frame"} if text else None

    lemma = _first_non_empty_value(
        _strip_str(data.get("lemma")),
        _strip_str(data.get("label")),
        _strip_str(data.get("name")),
        _strip_str(data.get("title")),
        _strip_str(data.get("value")),
    )
    if lemma is None:
        return None

    pos = _first_non_empty_value(_strip_str(data.get("pos")), default_pos)
    source = _first_non_empty_value(_strip_str(data.get("source")), "frame")

    features = data.get("features") if isinstance(data.get("features"), Mapping) else None

    out: dict[str, JSONValue] = {
        "lemma": lemma,
        "source": str(source),
    }
    if pos is not None:
        out["pos"] = str(pos)
    if _strip_str(data.get("qid")) is not None:
        out["qid"] = str(data["qid"])
    if _strip_str(data.get("id")) is not None and "qid" not in out:
        out["id"] = str(data["id"])
    if features:
        out["features"] = _to_json_value(dict(features))

    extra = {
        str(k): _to_json_value(v)
        for k, v in data.items()
        if k not in {"lemma", "label", "name", "title", "value", "pos", "source", "qid", "id", "features"}
    }
    if extra:
        out["extra"] = _to_json_value(extra)
    return out


def _normalize_time_value(raw: Any) -> Optional[JSONValue]:
    if raw is None:
        return None

    if isinstance(raw, int):
        return {"start_year": raw}

    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return None
        if _YEAR_RE.fullmatch(text):
            return {"start_year": int(text)}
        match = _DATE_RE.fullmatch(text)
        if match:
            return {
                "start_year": int(match.group("y")),
                "start_month": int(match.group("m")),
                "start_day": int(match.group("d")),
            }
        return {"label": text}

    data = _to_plain(raw)
    if not isinstance(data, Mapping):
        return {"label": str(data)}

    out: dict[str, JSONValue] = {}

    for key in ("start_year", "end_year", "start_month", "start_day", "end_month", "end_day"):
        value = data.get(key)
        if isinstance(value, int):
            out[key] = value
        elif isinstance(value, str) and value.strip().isdigit():
            out[key] = int(value.strip())

    approximate = data.get("approximate")
    if isinstance(approximate, bool):
        out["approximate"] = approximate

    label = _first_non_empty_value(
        _strip_str(data.get("label")),
        _strip_str(data.get("date")),
        _strip_str(data.get("value")),
    )
    if label is not None and not out:
        if _YEAR_RE.fullmatch(label):
            out["start_year"] = int(label)
        else:
            out["label"] = label

    extra = {
        str(k): _to_json_value(v)
        for k, v in data.items()
        if k not in {
            "start_year",
            "end_year",
            "start_month",
            "start_day",
            "end_month",
            "end_day",
            "approximate",
            "label",
            "date",
            "value",
        }
    }
    if extra:
        out["extra"] = _to_json_value(extra)

    return out or None


def _normalize_quantity_value(raw: Any) -> Optional[JSONValue]:
    if raw is None:
        return None

    if isinstance(raw, (int, float, str)):
        return raw

    data = _to_plain(raw)
    if isinstance(data, Mapping):
        return {str(k): _to_json_value(v) for k, v in data.items()}
    return str(data)


def _extract_first_string_list_item(value: Any) -> Optional[str]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            text = _strip_str(item)
            if text:
                return text
    return None


# ---------------------------------------------------------------------- #
# Slot-map finalization                                                  #
# ---------------------------------------------------------------------- #


def _maybe_add_common_modifiers(frame: Mapping[str, Any], slot_map: SlotMap) -> SlotMap:
    """
    Add shared optional semantic modifiers such as time/location/quantity when
    they are not already present.
    """
    out = dict(slot_map)

    if "time" not in out:
        time_value = _extract_time(frame)
        if time_value is not None:
            out["time"] = time_value

    if "location" not in out:
        location_value = _extract_location(frame)
        if location_value is not None:
            out["location"] = location_value

    if "quantity" not in out:
        quantity_value = _extract_quantity(frame)
        if quantity_value is not None:
            out["quantity"] = quantity_value

    return out


def _finalize_slot_map(slot_map: Mapping[str, Any]) -> SlotMap:
    if not isinstance(slot_map, Mapping):
        raise InvalidSlotMapError("slot_map must be a mapping.")

    out: SlotMap = {}
    for raw_key, raw_value in slot_map.items():
        key = _normalize_slot_name(str(raw_key))
        value = _compact_json_value(_to_json_value(raw_value))
        if value is None:
            continue
        out[key] = value

    if not out:
        raise InvalidSlotMapError("slot_map must not be empty.")

    return out


def _compact_json_value(value: JSONValue) -> Optional[JSONValue]:
    """
    Recursively drop empty/None containers while preserving valid scalar falsy
    values like 0 and False.
    """
    if value is None:
        return None

    if isinstance(value, str):
        value = value.strip()
        return value or None

    if isinstance(value, list):
        items = [_compact_json_value(v) for v in value]
        items = [v for v in items if v is not None]
        return items or None

    if isinstance(value, dict):
        compacted: dict[str, JSONValue] = {}
        for key, v in value.items():
            compact_v = _compact_json_value(v)
            if compact_v is not None:
                compacted[str(key)] = compact_v
        return compacted or None

    return value


__all__ = [
    "SlotMap",
    "FrameToSlotsError",
    "UnsupportedConstructionError",
    "MissingRequiredRoleError",
    "InvalidSlotMapError",
    "FrameToSlotsBridge",
    "frame_to_slots",
]