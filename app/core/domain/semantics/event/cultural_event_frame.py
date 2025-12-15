# semantics\event\cultural_event_frame.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from semantics.types import Entity, Event, Location, TimeSpan


@dataclass
class CulturalEventFrame:
    """
    Semantic frame for cultural events such as festivals, exhibitions,
    premieres, award ceremonies, and other arts / culture gatherings.

    The goal is to support Wikipedia-style lead sentences like:

        - "The Cannes Film Festival is an annual film festival held in Cannes, France."
        - "The Venice Biennale is a major contemporary art exhibition in Venice, Italy."
        - "The Academy Awards is an annual film awards ceremony presented by the Academy of Motion Picture Arts and Sciences."

    This frame is intended as a **high-level, language-independent summary**
    used as input to the NLG system. It does not perform any rendering by
    itself; downstream components (normalizers, engines, constructions)
    decide how to verbalize the information.

    Fields
    ======

    main_event:
        Core semantic representation of the cultural event episode.
        Typically an :class:`Event` with:

        * ``event_type`` like ``"festival"``, ``"exhibition"``,
          ``"awards_ceremony"``, ``"premiere"``, etc.
        * participants such as organisers, hosts, performers, and audience.
        * time span (dates) and location(s).

    label:
        Optional human-readable label for this specific instance, e.g.
        "2020 Cannes Film Festival", "68th Berlin International Film Festival".
        If omitted, downstream code can fall back to ``main_event.label`` /
        ``main_event.extra`` or other sources.

    cultural_event_kind:
        Coarse subtype within the cultural domain, used to guide lexical
        choice. Examples (not a closed list):

        * "festival"
        * "film_festival"
        * "music_festival"
        * "art_exhibition"
        * "book_fair"
        * "awards_ceremony"
        * "premiere"
        * "concert_series"

        This is language-neutral and typically realized as a lemma in the
        target language by the lexicon / morphology layer.

    domain_lemmas:
        High-level domain(s) of the event, expressed as language-neutral
        lemmas such as ``["film"]``, ``["music"]``, ``["theatre"]``,
        ``["literature"]``, ``["visual_art"]``. These help choose phrases
        like "film festival", "music festival", "art exhibition".

    event_series:
        Optional :class:`Entity` representing the recurring series or
        umbrella event this instance belongs to, e.g. the series
        "Cannes Film Festival" for the specific 2020 edition.

    edition_number:
        Optional integer giving the numbered edition within ``event_series``,
        e.g. ``73`` for "73rd Venice International Film Festival".
        Downstream code may render this with ordinals.

    organisers:
        List of :class:`Entity` objects representing organizing bodies,
        committees, or institutions (e.g. the Academy of Motion Picture Arts
        and Sciences, a municipal government, a festival association).

    host_location:
        Primary host location (typically a city or region) as a
        :class:`Location`. This is a coarse "host city" level and is
        separate from specific venues.

    venues:
        List of :class:`Location` objects representing specific venues such
        as theatres, halls, galleries, or campuses where the event is held.

    time_span:
        Optional :class:`TimeSpan` indicating the headline date range of
        the event (e.g. start/end dates of a festival edition). If omitted,
        downstream code may fall back to ``main_event.time``.

    recurrence:
        Short textual label describing how often the event occurs, e.g.
        "annual", "biennial", "monthly", "one_off". This is a coarse,
        language-neutral hint to help produce phrases like "an annual
        film festival".

    attendance_estimate:
        Optional integer estimate of attendance (e.g. number of visitors or
        spectators) for this edition, if known.

    attendance_year:
        Optional year associated with ``attendance_estimate`` (useful for
        long-running events where attendance figures are not for the
        current edition).

    key_participants:
        List of :class:`Entity` objects representing notable participants
        or roles that may be mentioned in summaries, e.g. guest of honour,
        curator, headlining performers, or juries.

    associated_events:
        List of :class:`Event` objects closely tied to the cultural event,
        such as award ceremonies, opening / closing ceremonies, or
        associated competitions.

    metrics:
        Machine-readable numeric or categorical indicators, stored as a
        free-form dictionary. Examples:

            {
                "number_of_films": 56,
                "number_of_competing_entries": 20,
                "number_of_countries": 15,
                "award_categories": 24,
            }

        Keys are project-specific; values should be JSON-serializable.

    attributes:
        Open-ended attribute map for additional structured information that
        does not warrant a dedicated field but may still be relevant for
        NLG or downstream systems. Example:

            {
                "theme": "Women in film",
                "motto": "Cinema for all",
                "focus_region": ["Latin America"],
            }

    extra:
        Free-form metadata that is preserved but not interpreted by the NLG
        system. Typical contents include source identifiers (e.g. Wikidata
        QIDs), raw source JSON blobs, provenance info, or debugging flags.
    """

    # Top-level discriminator for routing; kept out of __init__ so callers
    # do not need to pass it explicitly.
    frame_type: str = field(init=False, default="event.cultural")

    # Core subject -----------------------------------------------------------
    main_event: Event

    # Descriptive classification --------------------------------------------
    label: Optional[str] = None
    cultural_event_kind: Optional[str] = None
    domain_lemmas: List[str] = field(default_factory=list)

    # Relationship to a recurring series ------------------------------------
    event_series: Optional[Entity] = None
    edition_number: Optional[int] = None

    # Actors and locations ---------------------------------------------------
    organisers: List[Entity] = field(default_factory=list)
    host_location: Optional[Location] = None
    venues: List[Location] = field(default_factory=list)

    # Time and recurrence ----------------------------------------------------
    time_span: Optional[TimeSpan] = None
    recurrence: Optional[str] = None

    # Participation and associated events -----------------------------------
    attendance_estimate: Optional[int] = None
    attendance_year: Optional[int] = None
    key_participants: List[Entity] = field(default_factory=list)
    associated_events: List[Event] = field(default_factory=list)

    # Quantitative and qualitative extras -----------------------------------
    metrics: Dict[str, Any] = field(default_factory=dict)
    attributes: Dict[str, Any] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)


__all__ = ["CulturalEventFrame"]
