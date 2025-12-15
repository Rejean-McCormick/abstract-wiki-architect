# semantics\types.py
"""
semantics/types.py
------------------

Core semantic data structures for Abstract Wiki Architect.

This module defines small, typed Python data classes that represent
the *meaning-level* inputs to the NLG system, independently of any
particular language, engine, or construction.

Typical usage
=============

The idea is that higher-level code (CSV readers, AW/Z-bridges, etc.)
will normalize loose dictionaries into these types and then pass them
to the router / construction layer:

    from semantics.types import Entity, BioFrame, Event, TimeSpan

    marie = Entity(
        id="Q7186",
        name="Marie Curie",
        gender="female",
        human=True,
        extra={"wikidata_qid": "Q7186"},
    )

    birth_event = Event(
        id="E1",
        event_type="birth",
        participants={"subject": marie},
        time=TimeSpan(start_year=1867),
        location=Location(id="L1", name="Warsaw"),
    )

    frame = BioFrame(
        main_entity=marie,
        primary_profession_lemmas=["physicist"],
        nationality_lemmas=["polish"],
        birth_event=birth_event,
    )

The rendering pipeline can then choose constructions and morphology
based on these semantic objects, rather than directly on CSV columns
or ad-hoc dictionaries.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


# ---------------------------------------------------------------------------
# Base Protocol
# ---------------------------------------------------------------------------

@runtime_checkable
class Frame(Protocol):
    """
    Protocol for any semantic frame.
    Must at least carry a canonical type identifier.
    """
    frame_type: str


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
    lemmas: List[str] = field(default_factory=list)
    features: Dict[str, Any] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)


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


@dataclass
class Event:
    """
    A semantic event or state.

    This is generic enough to cover:
        - Birth / death events
        - Discoveries, awards, appointments
        - Generic intransitive / transitive events

    Fields:
        id:
            Stable identifier for the event, if any.
        event_type:
            High-level label, e.g. "birth", "death", "discovery",
            "award", "generic". Left as a free string so projects can
            define their own inventory.
        participants:
            Mapping from role label → Entity. For example:
                {
                    "subject": Entity(...),
                    "object": Entity(...),
                    "beneficiary": Entity(...),
                }
            Role labels are free-form strings (e.g. "agent", "patient",
            "subject", "recipient") which can later be normalized.
        time:
            Optional TimeSpan describing when the event happened.
        location:
            Optional Location for where the event took place.
        properties:
            Arbitrary additional semantic properties, e.g.:
                {
                    "instrument": Entity(...),
                    "manner": "secretly"
                }
        extra:
            Arbitrary metadata, e.g. original source structure.
    """

    id: Optional[str] = None
    event_type: str = "generic"
    participants: Dict[str, Entity] = field(default_factory=dict)
    time: Optional[TimeSpan] = None
    location: Optional[Location] = None
    properties: Dict[str, Any] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Higher-level frames
# ---------------------------------------------------------------------------


@dataclass
class BioFrame:
    """
    A high-level semantic frame for a simple biography / entity summary.

    This is designed to support first-sentence Wikipedia-style bios, with
    enough structure to drive different constructions (equatives,
    attributive clauses, etc.) across languages.

    Fields:
        main_entity:
            The entity the biography is about (e.g. Marie Curie).
        frame_type:
            Discriminator field ("bio") for the Frame protocol.
        primary_profession_lemmas:
            List of lemmas representing the primary profession(s)
            (e.g. ["physicist"]). These are language-neutral; the
            realization will pick the right lexeme per language.
        nationality_lemmas:
            List of lemmas representing nationalities (e.g. ["polish"]).
        birth_event:
            Optional Event of type "birth".
        death_event:
            Optional Event of type "death".
        other_events:
            List of other salient events (discoveries, awards, roles…).
        attributes:
            Arbitrary attribute map for the main entity, e.g.:
                {"field": ["physics", "chemistry"], "known_for": [...]}
        extra:
            Arbitrary metadata (e.g. original JSON from AW, Wikidata IDs).

    Notes:
        - This is intentionally biased towards person bios; for other
          entity types you may define additional frame types later, or
          simply reuse `Event` + `Entity` directly.
    """

    main_entity: Entity
    frame_type: str = "bio"
    primary_profession_lemmas: List[str] = field(default_factory=list)
    nationality_lemmas: List[str] = field(default_factory=list)
    birth_event: Optional[Event] = None
    death_event: Optional[Event] = None
    other_events: List[Event] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Type aliases and exports
# ---------------------------------------------------------------------------

# Generic alias for "something we can render as a sentence or series of sentences"
SemanticFrame = BioFrame  # can be extended to a Union[.] in the future

__all__ = [
    "Frame",
    "Entity",
    "Location",
    "TimeSpan",
    "Event",
    "BioFrame",
    "SemanticFrame",
]