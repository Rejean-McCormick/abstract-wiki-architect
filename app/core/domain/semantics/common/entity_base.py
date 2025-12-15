# semantics\common\entity_base.py
"""
semantics/common/entity_base.py
-------------------------------

Core, reusable semantic units for entities, locations and time spans.

This module is intentionally small and stable. It provides the basic
objects that all frame families (biography, event, organization, etc.)
can share without pulling in any higher-level frame logic.

Typical usage
=============

    from semantics.common.entity_base import Entity, Location, TimeSpan

    marie = Entity(
        id="Q7186",
        name="Marie Curie",
        gender="female",
        human=True,
        extra={"wikidata_qid": "Q7186"},
    )

    warsaw = Location(id="L1", name="Warsaw", kind="city", country_code="PL")

    lifespan = TimeSpan(start_year=1867, end_year=1934)

The higher-level frame types (BioFrame, EventFrame, etc.) can then refer
to these basic units without re-defining them.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Mapping, Optional, Type, TypeVar


# ---------------------------------------------------------------------------
# Core semantic units
# ---------------------------------------------------------------------------


@dataclass
class Entity:
    """
    A discourse entity (person, organization, place, abstract thing).

    Fields:
        id:
            Stable identifier, e.g. a Wikidata QID ("Q42"). Optional.
        name:
            Canonical label to use when no localized surface form is
            available (e.g. "Marie Curie").
        gender:
            Coarse gender category for persons (e.g. "female", "male",
            "nonbinary", "unknown"). Left as a free string so that
            different projects can choose their own inventory.
        human:
            Whether this entity is a human. Useful for pronoun choice,
            plural markers, etc.
        entity_type:
            Optional coarse type hint ("person", "organization",
            "place", "country", "city", ...).
        lemmas:
            Optional list of lexeme lemmas associated with the entity,
            e.g. ["physicist", "chemist"] for a person.
        features:
            Arbitrary feature dictionary (e.g. for grammatical category,
            animacy, number, etc.) used by morphology or constructions.
        extra:
            Arbitrary metadata, e.g. Wikidata IDs, ISO codes, etc.

    Notes:
        - `name` is typically the surface label; if you need a lemma for
          predicate-like use ("to Curie-ify"), that belongs in `lemmas`
          or `extra`.
    """

    id: Optional[str] = None
    name: str = ""
    gender: str = "unknown"
    human: bool = False
    entity_type: Optional[str] = None
    lemmas: list[str] = field(default_factory=list)
    features: Dict[str, Any] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Lightweight conversion helpers
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """
        Return a JSON-serializable dict representation of this Entity.

        Nested dataclasses (if any) are left as-is; callers that need a
        fully flattened structure should post-process the result.
        """
        return asdict(self)

    @classmethod
    def from_dict(cls: Type["Entity"], data: Mapping[str, Any]) -> "Entity":
        """
        Construct an Entity from a loose mapping.

        Unknown keys are ignored; missing keys fall back to dataclass
        defaults. This is intended for normalizing AW/Z style records.
        """
        return cls(
            id=data.get("id"),
            name=str(data.get("name", "")),
            gender=str(data.get("gender", "unknown")),
            human=bool(data.get("human", False)),
            entity_type=data.get("entity_type") or data.get("type"),
            lemmas=list(data.get("lemmas", [])),
            features=dict(data.get("features", {})),
            extra=dict(data.get("extra", {})),
        )


@dataclass
class Location:
    """
    A location entity (city, country, region, etc.).

    This is intentionally light; you can also use `Entity` directly
    for locations. This separate type is provided mainly so code can
    express intent more clearly.

    Fields:
        id:
            Stable identifier, e.g. a QID or geocode.
        name:
            Human-readable label (e.g. "Paris").
        kind:
            Optional location kind ("city", "country", "region", ...).
        country_code:
            Optional ISO country code (e.g. "FR").
        features:
            Arbitrary feature dictionary, e.g. for preposition choice.
        extra:
            Arbitrary metadata.
    """

    id: Optional[str] = None
    name: str = ""
    kind: Optional[str] = None
    country_code: Optional[str] = None
    features: Dict[str, Any] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """
        Return a JSON-serializable dict representation of this Location.
        """
        return asdict(self)

    @classmethod
    def from_dict(cls: Type["Location"], data: Mapping[str, Any]) -> "Location":
        """
        Construct a Location from a loose mapping.

        Unknown keys are ignored; missing keys fall back to dataclass
        defaults.
        """
        return cls(
            id=data.get("id"),
            name=str(data.get("name", "")),
            kind=data.get("kind") or data.get("location_type"),
            country_code=data.get("country_code") or data.get("iso_country"),
            features=dict(data.get("features", {})),
            extra=dict(data.get("extra", {})),
        )


@dataclass
class TimeSpan:
    """
    A simple time span (possibly a single year or date).

    We keep this deliberately coarse for now; you can extend it to
    full ISO date/time strings if needed.

    Fields:
        start_year:
            Starting year, e.g. 1867. For a single date, this is the
            main year of interest.
        end_year:
            Optional end year, e.g. 1934 for a lifespan.
        start_month:
            Optional month (1-12) for more precise dates.
        start_day:
            Optional day (1-31).
        end_month, end_day:
            Optional end-month/day for intervals.
        approximate:
            True if the dates are approximate or inferred.
        extra:
            Arbitrary metadata (full ISO strings, calendar system, etc.).
    """

    start_year: Optional[int] = None
    end_year: Optional[int] = None
    start_month: Optional[int] = None
    start_day: Optional[int] = None
    end_month: Optional[int] = None
    end_day: Optional[int] = None
    approximate: bool = False
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """
        Return a JSON-serializable dict representation of this TimeSpan.
        """
        return asdict(self)

    @classmethod
    def from_dict(cls: Type["TimeSpan"], data: Mapping[str, Any]) -> "TimeSpan":
        """
        Construct a TimeSpan from a loose mapping.

        The mapping may use either explicit numeric fields (start_year,
        end_year, etc.) or, in simple cases, a single `year` key which
        is treated as `start_year`.
        """
        # Allow a convenience single "year" field.
        start_year = data.get("start_year", data.get("year"))
        end_year = data.get("end_year")

        return cls(
            start_year=int(start_year) if start_year is not None else None,
            end_year=int(end_year) if end_year is not None else None,
            start_month=data.get("start_month"),
            start_day=data.get("start_day"),
            end_month=data.get("end_month"),
            end_day=data.get("end_day"),
            approximate=bool(data.get("approximate", False)),
            extra=dict(data.get("extra", {})),
        )


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------

_EntityLike = TypeVar("_EntityLike", bound=Entity)
_LocationLike = TypeVar("_LocationLike", bound=Location)
_TimeSpanLike = TypeVar("_TimeSpanLike", bound=TimeSpan)


def ensure_entity(
    value: Entity | Mapping[str, Any] | None,
    cls: Type[_EntityLike] = Entity,  # allows subclasses
) -> Optional[_EntityLike]:
    """
    Normalize a value to an Entity (or subclass) instance.

    Accepts:
        - Entity (or subclass) → returned unchanged
        - Mapping[str, Any]    → converted via Entity.from_dict(...)
        - None                 → None
    """
    if value is None:
        return None
    if isinstance(value, cls):
        return value
    if isinstance(value, Entity) and cls is Entity:
        # Exact Entity instance and no subclass requested.
        return value  # type: ignore[return-value]
    if isinstance(value, Mapping):
        return cls.from_dict(value)  # type: ignore[return-value]
    raise TypeError(f"Cannot coerce value of type {type(value)!r} to {cls.__name__}")


def ensure_location(
    value: Location | Mapping[str, Any] | None,
    cls: Type[_LocationLike] = Location,
) -> Optional[_LocationLike]:
    """
    Normalize a value to a Location (or subclass) instance.

    Accepts:
        - Location (or subclass) → returned unchanged
        - Mapping[str, Any]      → converted via Location.from_dict(...)
        - None                   → None
    """
    if value is None:
        return None
    if isinstance(value, cls):
        return value
    if isinstance(value, Location) and cls is Location:
        return value  # type: ignore[return-value]
    if isinstance(value, Mapping):
        return cls.from_dict(value)  # type: ignore[return-value]
    raise TypeError(f"Cannot coerce value of type {type(value)!r} to {cls.__name__}")


def ensure_time_span(
    value: TimeSpan | Mapping[str, Any] | None,
    cls: Type[_TimeSpanLike] = TimeSpan,
) -> Optional[_TimeSpanLike]:
    """
    Normalize a value to a TimeSpan (or subclass) instance.

    Accepts:
        - TimeSpan (or subclass) → returned unchanged
        - Mapping[str, Any]      → converted via TimeSpan.from_dict(...)
        - None                   → None
    """
    if value is None:
        return None
    if isinstance(value, cls):
        return value
    if isinstance(value, TimeSpan) and cls is TimeSpan:
        return value  # type: ignore[return-value]
    if isinstance(value, Mapping):
        return cls.from_dict(value)  # type: ignore[return-value]
    raise TypeError(f"Cannot coerce value of type {type(value)!r} to {cls.__name__}")


__all__ = [
    "Entity",
    "Location",
    "TimeSpan",
    "ensure_entity",
    "ensure_location",
    "ensure_time_span",
]
