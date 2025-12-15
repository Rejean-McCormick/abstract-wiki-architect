# semantics\entity\facility_frame.py
# semantics/entity/facility_frame.py

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from semantics.common.entity_base import EntityFrameBase
from semantics.types import Entity, Event, Location, TimeSpan


@dataclass
class FacilityFrame(EntityFrameBase):
    """
    High-level semantic frame for a facility / infrastructure entity.

    This covers things like buildings, bridges, dams, airports, railway
    stations, power plants, stadiums, monuments, etc.  It is intended
    for first-sentence / short-intro Wikipedia-style summaries such as:

        "The Golden Gate Bridge is a suspension bridge spanning the
        Golden Gate strait in San Francisco, California."
        "Old Trafford is a football stadium in Greater Manchester,
        England, and the home of Manchester United."

    The frame is deliberately coarse and language-independent.  It is
    meant to be populated by upstream normalization code (e.g. from
    Wikidata / CSV / JSON) and then consumed by the NLG layer.

    Inheritance
    ===========
    The class extends ``EntityFrameBase``, which provides the core
    entity-centric slots such as:

        - main_entity: Entity
            The facility itself (canonical label, IDs, etc.).
        - extra: dict[str, Any]
            Free-form metadata hook for callers.

    Fields
    ======
    frame_type:
        Stable identifier for this frame family.  Engines and routers
        can use this to dispatch to facility-specific logic.  Kept as a
        plain string rather than an Enum to keep the public API simple.

    facility_kinds:
        List of coarse type labels for the facility, in lemma form,
        such as:

            ["bridge"]
            ["stadium"]
            ["airport"]
            ["hydroelectric dam"]

        The first element is treated as the primary kind; additional
        elements may be used for more specific realizations.

    function_lemmas:
        Optional list of lemmas describing the facility's primary
        function or usage, e.g.:

            ["road", "railway"]          # road / rail bridge
            ["multi-purpose"]            # multi-purpose stadium
            ["international", "cargo"]   # international cargo airport

        These are hints for downstream engines; they are not required.

    location:
        Optional ``Location`` object capturing the facility's main
        geographic anchor (city / region / country label, codes, etc.).
        This is typically what an intro sentence will realize in a
        locative phrase ("in Paris, France").

    location_hierarchy:
        Optional list of additional ``Location`` objects representing a
        coarse hierarchy around the facility, ordered from more specific
        to more general, e.g.:

            [
                Location(name="Wembley", kind="district"),
                Location(name="London", kind="city"),
                Location(name="England", kind="country"),
            ]

        Engines may use this to choose how much of the hierarchy to
        mention given sentence-length constraints.

    construction_period:
        Optional ``TimeSpan`` describing when the facility was built
        (planning, construction, major rebuilds).  For simple cases this
        may be a single year:

            TimeSpan(start_year=1931, end_year=1937)

        More complex pipelines can store additional calendar detail
        in ``TimeSpan.extra``.

    opening_date:
        Optional ``TimeSpan`` for the official opening / inauguration
        date, distinct from construction.  For many facilities this is a
        single year or full date.

    closure_date:
        Optional ``TimeSpan`` for closure / decommissioning, if the
        facility is no longer in regular use.

    architects:
        Optional list of ``Entity`` objects representing architects,
        designers or principal engineers associated with the facility.

    owners:
        Optional list of ``Entity`` objects representing legal owners
        (companies, public authorities, organizations).

    operators:
        Optional list of ``Entity`` objects representing day-to-day
        operators (railway companies, airport operators, sports clubs).

    capacity:
        Optional integer capacity associated with the facility.  The
        interpretation depends on ``capacity_kind`` (seats, passengers
        per day, megawatts, etc.).

        The value is an abstract, unitless number; upstream code is
        responsible for choosing a consistent convention (e.g. raw
        integer representing the count).

    capacity_kind:
        Optional free-form label describing what ``capacity`` refers to,
        for example:

            "seating"
            "spectators"
            "passengers_per_year"
            "megawatts"

        Engines can use this for wording ("seating capacity of 75,000",
        "installed capacity of 500 MW", etc.).

    notable_events:
        Optional list of ``Event`` objects representing salient events
        that happened at the facility (disasters, major tournaments,
        openings, reopenings, etc.).  For simple intros, engines may
        only need to know that such events exist, but richer summaries
        can mine them for content.

    notes:
        Optional free-text notes that may help with debugging, manual
        inspection, or temporary annotations in pipelines.  Not intended
        for direct realization.

    extra:
        Inherited from ``EntityFrameBase``; can store arbitrary
        metadata (IDs, source blobs, flags) without changing the public
        interface.
    """

    # ------------------------------------------------------------------
    # Frame identity
    # ------------------------------------------------------------------

    #: Stable frame family identifier used by routers / engines.
    frame_type: str = "facility"

    # ------------------------------------------------------------------
    # Facility-specific semantic slots
    # ------------------------------------------------------------------

    facility_kinds: List[str] = field(default_factory=list)
    function_lemmas: List[str] = field(default_factory=list)

    location: Optional[Location] = None
    location_hierarchy: List[Location] = field(default_factory=list)

    construction_period: Optional[TimeSpan] = None
    opening_date: Optional[TimeSpan] = None
    closure_date: Optional[TimeSpan] = None

    architects: List[Entity] = field(default_factory=list)
    owners: List[Entity] = field(default_factory=list)
    operators: List[Entity] = field(default_factory=list)

    capacity: Optional[int] = None
    capacity_kind: Optional[str] = None

    notable_events: List[Event] = field(default_factory=list)

    # Optional free-form notes; not for direct realization by default.
    notes: Optional[str] = None

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    @property
    def primary_kind(self) -> str:
        """
        Return the primary facility kind, or an empty string if unknown.

        This is a convenience for engines that want a single coarse type
        without having to inspect ``facility_kinds`` directly.
        """
        return self.facility_kinds[0] if self.facility_kinds else ""

    def to_dict(self) -> Dict[str, Any]:
        """
        Lightweight, explicit dictionary view of the main slots.

        This is intended for debugging, JSON dumps, or lightweight
        tooling.  It intentionally keeps a shallow structure and does not
        attempt to recursively serialize nested dataclasses; callers who
        need that can use dataclasses.asdict or a custom encoder.

        The exact set of keys is kept small and stable on purpose.
        """
        return {
            "frame_type": self.frame_type,
            "main_entity": self.main_entity,
            "facility_kinds": list(self.facility_kinds),
            "function_lemmas": list(self.function_lemmas),
            "location": self.location,
            "location_hierarchy": list(self.location_hierarchy),
            "construction_period": self.construction_period,
            "opening_date": self.opening_date,
            "closure_date": self.closure_date,
            "architects": list(self.architects),
            "owners": list(self.owners),
            "operators": list(self.operators),
            "capacity": self.capacity,
            "capacity_kind": self.capacity_kind,
            "notable_events": list(self.notable_events),
            "notes": self.notes,
            "extra": dict(self.extra),
        }


__all__ = ["FacilityFrame"]
