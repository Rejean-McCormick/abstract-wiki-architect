# app/core/domain/semantics/types.py
"""
Meaning-level semantic dataclasses.

This module intentionally stays below the planner / construction runtime.
It defines reusable semantic objects that upstream normalizers can build
from loose payloads, and that downstream bridge/planner code can inspect
without depending on any particular renderer backend.

Design goals:
- language-neutral
- construction-neutral
- tolerant of legacy / AW-style payloads
- lightweight and easy to serialize
- backward-compatible with current bio-centric callers while remaining
  usable for broader frame families
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Mapping, Optional, Protocol, TypeAlias, runtime_checkable


# ---------------------------------------------------------------------------
# Small internal helpers
# ---------------------------------------------------------------------------


def _clean_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        return value or None
    value = str(value).strip()
    return value or None


def _clean_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _copy_dict(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _copy_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, (list, tuple, set)) else []


def _first_non_empty(*values: Any) -> Optional[str]:
    for value in values:
        cleaned = _clean_str(value)
        if cleaned is not None:
            return cleaned
    return None


# ---------------------------------------------------------------------------
# Base Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class Frame(Protocol):
    """
    Protocol for semantic frames used before planning.

    Every frame must expose a stable `frame_type`. The optional metadata
    bags are intentionally loose to keep normalization tolerant of varied
    upstream payloads.
    """

    frame_type: str


# ---------------------------------------------------------------------------
# Core semantic units
# ---------------------------------------------------------------------------


@dataclass
class Entity:
    """
    A discourse entity (person, organization, place, abstract thing).

    Notes:
    - `id` is the general stable identifier for this project.
    - `qid` is kept as an explicit compatibility field because several
      legacy paths still refer to Wikidata-like IDs under that name.
    - `lemmas` are language-neutral lexical hints, not realized forms.
    """

    id: Optional[str] = None
    qid: Optional[str] = None
    name: str = ""
    gender: str = "unknown"
    human: bool = False
    entity_type: Optional[str] = None
    lemmas: list[str] = field(default_factory=list)
    features: Dict[str, Any] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.id = _clean_str(self.id)
        self.qid = _clean_str(self.qid)
        self.name = _clean_str(self.name) or ""
        self.gender = _clean_str(self.gender) or "unknown"
        self.entity_type = _clean_str(self.entity_type)

        self.lemmas = [str(v).strip() for v in self.lemmas if str(v).strip()]
        self.features = dict(self.features)
        self.extra = dict(self.extra)

        inferred_qid = _first_non_empty(
            self.qid,
            self.extra.get("qid"),
            self.extra.get("wikidata_qid"),
        )
        if inferred_qid:
            self.qid = inferred_qid

        if not self.id and self.qid:
            self.id = self.qid

        if self.id and not self.qid and self.id.startswith("Q"):
            self.qid = self.id

    @property
    def canonical_id(self) -> Optional[str]:
        return self.id or self.qid

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Entity":
        extra = _copy_dict(data.get("extra"))
        for legacy_key in ("wikidata_qid",):
            if legacy_key in data and legacy_key not in extra:
                extra[legacy_key] = data.get(legacy_key)

        return cls(
            id=_first_non_empty(data.get("id"), data.get("entity_id"), data.get("qid")),
            qid=_first_non_empty(data.get("qid"), data.get("wikidata_qid")),
            name=_first_non_empty(data.get("name"), data.get("label")) or "",
            gender=_first_non_empty(data.get("gender"), "unknown") or "unknown",
            human=bool(data.get("human", False)),
            entity_type=_first_non_empty(data.get("entity_type"), data.get("type")),
            lemmas=_copy_list(data.get("lemmas")),
            features=_copy_dict(data.get("features")),
            extra=extra,
        )


@dataclass
class Location:
    """
    A location entity (city, country, region, venue, etc.).
    """

    id: Optional[str] = None
    name: str = ""
    kind: Optional[str] = None
    country_code: Optional[str] = None
    features: Dict[str, Any] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.id = _clean_str(self.id)
        self.name = _clean_str(self.name) or ""
        self.kind = _clean_str(self.kind)
        self.country_code = _clean_str(self.country_code)
        self.features = dict(self.features)
        self.extra = dict(self.extra)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Location":
        return cls(
            id=_first_non_empty(data.get("id"), data.get("location_id")),
            name=_first_non_empty(data.get("name"), data.get("label")) or "",
            kind=_first_non_empty(data.get("kind"), data.get("location_type"), data.get("type")),
            country_code=_first_non_empty(data.get("country_code"), data.get("iso_country")),
            features=_copy_dict(data.get("features")),
            extra=_copy_dict(data.get("extra")),
        )


@dataclass
class TimeSpan:
    """
    A coarse time span or date-like object.

    This stays intentionally lightweight. For richer precision, callers may
    store ISO strings or source-system data inside `extra`.
    """

    start_year: Optional[int] = None
    end_year: Optional[int] = None
    start_month: Optional[int] = None
    start_day: Optional[int] = None
    end_month: Optional[int] = None
    end_day: Optional[int] = None
    approximate: bool = False
    extra: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.start_year = _clean_int(self.start_year)
        self.end_year = _clean_int(self.end_year)
        self.start_month = _clean_int(self.start_month)
        self.start_day = _clean_int(self.start_day)
        self.end_month = _clean_int(self.end_month)
        self.end_day = _clean_int(self.end_day)
        self.approximate = bool(self.approximate)
        self.extra = dict(self.extra)

        for field_name, value, low, high in (
            ("start_month", self.start_month, 1, 12),
            ("end_month", self.end_month, 1, 12),
            ("start_day", self.start_day, 1, 31),
            ("end_day", self.end_day, 1, 31),
        ):
            if value is not None and not (low <= value <= high):
                raise ValueError(f"{field_name} must be between {low} and {high}")

    @property
    def is_point(self) -> bool:
        return self.end_year is None and self.end_month is None and self.end_day is None

    @property
    def is_range(self) -> bool:
        return any(v is not None for v in (self.end_year, self.end_month, self.end_day))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TimeSpan":
        return cls(
            start_year=data.get("start_year", data.get("year")),
            end_year=data.get("end_year"),
            start_month=data.get("start_month"),
            start_day=data.get("start_day"),
            end_month=data.get("end_month"),
            end_day=data.get("end_day"),
            approximate=bool(data.get("approximate", False)),
            extra=_copy_dict(data.get("extra")),
        )


# ---------------------------------------------------------------------------
# Coercion helpers
# ---------------------------------------------------------------------------


def ensure_entity(value: Entity | Mapping[str, Any] | None) -> Optional[Entity]:
    if value is None:
        return None
    if isinstance(value, Entity):
        return value
    if isinstance(value, Mapping):
        return Entity.from_dict(value)
    raise TypeError(f"Cannot coerce value of type {type(value)!r} to Entity")


def ensure_location(value: Location | Mapping[str, Any] | None) -> Optional[Location]:
    if value is None:
        return None
    if isinstance(value, Location):
        return value
    if isinstance(value, Mapping):
        return Location.from_dict(value)
    raise TypeError(f"Cannot coerce value of type {type(value)!r} to Location")


def ensure_time_span(value: TimeSpan | Mapping[str, Any] | None) -> Optional[TimeSpan]:
    if value is None:
        return None
    if isinstance(value, TimeSpan):
        return value
    if isinstance(value, Mapping):
        return TimeSpan.from_dict(value)
    raise TypeError(f"Cannot coerce value of type {type(value)!r} to TimeSpan")


ParticipantValue: TypeAlias = Entity | list[Entity] | Any


def _ensure_participant(value: Any) -> ParticipantValue:
    if isinstance(value, Entity):
        return value
    if isinstance(value, Mapping):
        return Entity.from_dict(value)
    if isinstance(value, list):
        return [ensure_entity(v) if isinstance(v, (Entity, Mapping)) else v for v in value]
    if isinstance(value, tuple):
        return [ensure_entity(v) if isinstance(v, (Entity, Mapping)) else v for v in value]
    return value


# ---------------------------------------------------------------------------
# Event semantics
# ---------------------------------------------------------------------------


@dataclass
class Event:
    """
    Generic semantic event or state.

    This remains intentionally broad so it can cover birth/death events,
    discoveries, appointments, awards, generic predicates, and other
    event-like facts without forcing construction decisions at this layer.
    """

    id: Optional[str] = None
    event_type: str = "generic"
    participants: Dict[str, ParticipantValue] = field(default_factory=dict)
    time: Optional[TimeSpan] = None
    location: Optional[Location] = None
    properties: Dict[str, Any] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)
    meta: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.id = _clean_str(self.id)
        self.event_type = _clean_str(self.event_type) or "generic"
        self.participants = {
            str(role): _ensure_participant(value)
            for role, value in dict(self.participants).items()
        }
        self.time = ensure_time_span(self.time)
        self.location = ensure_location(self.location)
        self.properties = dict(self.properties)
        self.extra = dict(self.extra)
        self.meta = dict(self.meta)

    @property
    def frame_type(self) -> str:
        """
        Expose event instances as frame-like objects for generic callers.

        For event semantics, the most useful discriminator is usually the
        event subtype itself (e.g. "birth", "award", "event.election").
        """
        return self.event_type

    @property
    def subject(self) -> Optional[Entity]:
        value = self.participants.get("subject")
        return value if isinstance(value, Entity) else None

    @subject.setter
    def subject(self, value: Entity | Mapping[str, Any] | None) -> None:
        if value is None:
            self.participants.pop("subject", None)
            return
        ensured = ensure_entity(value)
        if ensured is None:
            self.participants.pop("subject", None)
            return
        self.participants["subject"] = ensured

    @property
    def main_entity(self) -> Optional[Entity]:
        return self.subject

    @property
    def name(self) -> str:
        subj = self.subject
        return subj.name if subj is not None else ""

    @property
    def qid(self) -> Optional[str]:
        subj = self.subject
        return subj.qid if subj is not None else None

    @property
    def gender(self) -> Optional[str]:
        subj = self.subject
        return subj.gender if subj is not None else None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Event":
        participants_in = data.get("participants")
        participants: Dict[str, ParticipantValue] = {}
        if isinstance(participants_in, Mapping):
            participants = {
                str(role): _ensure_participant(value)
                for role, value in participants_in.items()
            }

        return cls(
            id=_first_non_empty(data.get("id"), data.get("event_id")),
            event_type=_first_non_empty(data.get("event_type"), data.get("frame_type"), "generic") or "generic",
            participants=participants,
            time=ensure_time_span(data.get("time")),
            location=ensure_location(data.get("location")),
            properties=_copy_dict(data.get("properties")),
            extra=_copy_dict(data.get("extra")),
            meta=_copy_dict(data.get("meta")),
        )


# ---------------------------------------------------------------------------
# Higher-level frames
# ---------------------------------------------------------------------------


@dataclass
class BioFrame:
    """
    High-level semantic frame for a biography / entity-summary sentence.

    This stays deliberately flexible:
    - `frame_type` defaults to "bio" but may carry more specific family IDs.
    - `subject` is exposed as a compatibility alias for older code paths.
    - `name`, `qid`, `gender`, `profession`, and `nationality` properties
      support legacy discourse and routing logic.
    """

    main_entity: Entity
    frame_type: str = "bio"
    primary_profession_lemmas: list[str] = field(default_factory=list)
    nationality_lemmas: list[str] = field(default_factory=list)
    birth_event: Optional[Event] = None
    death_event: Optional[Event] = None
    other_events: list[Event] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)
    meta: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        ensured = ensure_entity(self.main_entity)
        if ensured is None:
            raise ValueError("BioFrame.main_entity is required")
        self.main_entity = ensured

        self.frame_type = _clean_str(self.frame_type) or "bio"
        self.primary_profession_lemmas = [
            str(v).strip()
            for v in self.primary_profession_lemmas
            if str(v).strip()
        ]
        self.nationality_lemmas = [
            str(v).strip()
            for v in self.nationality_lemmas
            if str(v).strip()
        ]

        self.birth_event = Event.from_dict(self.birth_event) if isinstance(self.birth_event, Mapping) else self.birth_event
        self.death_event = Event.from_dict(self.death_event) if isinstance(self.death_event, Mapping) else self.death_event
        self.other_events = [
            Event.from_dict(v) if isinstance(v, Mapping) else v
            for v in list(self.other_events)
        ]

        self.attributes = dict(self.attributes)
        self.extra = dict(self.extra)
        self.meta = dict(self.meta)

    @property
    def subject(self) -> Entity:
        return self.main_entity

    @subject.setter
    def subject(self, value: Entity | Mapping[str, Any]) -> None:
        ensured = ensure_entity(value)
        if ensured is None:
            raise ValueError("BioFrame.subject cannot be None")
        self.main_entity = ensured

    @property
    def name(self) -> str:
        return self.main_entity.name

    @name.setter
    def name(self, value: str) -> None:
        self.main_entity.name = _clean_str(value) or ""

    @property
    def qid(self) -> Optional[str]:
        return self.main_entity.qid

    @property
    def gender(self) -> str:
        return self.main_entity.gender

    @property
    def profession(self) -> Optional[str]:
        return self.primary_profession_lemmas[0] if self.primary_profession_lemmas else None

    @property
    def nationality(self) -> Optional[str]:
        return self.nationality_lemmas[0] if self.nationality_lemmas else None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "BioFrame":
        subject_data = data.get("main_entity") or data.get("subject")
        if isinstance(subject_data, Mapping):
            main_entity = Entity.from_dict(subject_data)
        elif isinstance(subject_data, Entity):
            main_entity = subject_data
        else:
            # Legacy flat payload compatibility.
            main_entity = Entity.from_dict(
                {
                    "id": data.get("id"),
                    "qid": data.get("qid"),
                    "name": data.get("name"),
                    "gender": data.get("gender"),
                    "human": data.get("human", True),
                    "entity_type": data.get("entity_type"),
                    "lemmas": data.get("lemmas"),
                    "features": data.get("features"),
                    "extra": data.get("entity_extra", {}),
                }
            )

        professions = _copy_list(data.get("primary_profession_lemmas"))
        if not professions:
            professions = _copy_list(data.get("professions"))
        if not professions:
            profession = _first_non_empty(data.get("profession"), data.get("profession_lemma"))
            professions = [profession] if profession else []

        nationalities = _copy_list(data.get("nationality_lemmas"))
        if not nationalities:
            nationalities = _copy_list(data.get("nationalities"))
        if not nationalities:
            nationality = _first_non_empty(data.get("nationality"), data.get("nationality_lemma"))
            nationalities = [nationality] if nationality else []

        attributes = _copy_dict(data.get("attributes"))
        if not attributes and isinstance(data.get("properties"), Mapping):
            attributes = dict(data["properties"])

        return cls(
            main_entity=main_entity,
            frame_type=_first_non_empty(data.get("frame_type"), "bio") or "bio",
            primary_profession_lemmas=[str(v).strip() for v in professions if str(v).strip()],
            nationality_lemmas=[str(v).strip() for v in nationalities if str(v).strip()],
            birth_event=Event.from_dict(data["birth_event"]) if isinstance(data.get("birth_event"), Mapping) else data.get("birth_event"),
            death_event=Event.from_dict(data["death_event"]) if isinstance(data.get("death_event"), Mapping) else data.get("death_event"),
            other_events=[
                Event.from_dict(v) if isinstance(v, Mapping) else v
                for v in _copy_list(data.get("other_events"))
            ],
            attributes=attributes,
            extra=_copy_dict(data.get("extra")),
            meta=_copy_dict(data.get("meta")),
        )


# ---------------------------------------------------------------------------
# Type aliases and exports
# ---------------------------------------------------------------------------

SemanticFrame: TypeAlias = BioFrame | Event

__all__ = [
    "Frame",
    "Entity",
    "Location",
    "TimeSpan",
    "Event",
    "BioFrame",
    "SemanticFrame",
    "ParticipantValue",
    "ensure_entity",
    "ensure_location",
    "ensure_time_span",
]