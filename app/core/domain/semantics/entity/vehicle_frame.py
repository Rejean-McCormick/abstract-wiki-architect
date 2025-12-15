# semantics\entity\vehicle_frame.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, List, Optional

from semantics.types import Entity, Location, TimeSpan


@dataclass
class VehicleFrame:
    """
    Vehicle frame.

    High-level semantic frame for Wikipedia-style summaries of **ships, boats,
    submarines, aircraft, helicopters, locomotives, multiple units, railway
    cars, motor vehicles, spacecraft, and similar vehicles or craft**.

    The goal is to capture enough structure to support sentences such as:

        - "HMS Dreadnought was a British battleship of the Royal Navy."
        - "Apollo 11 was a United States spaceflight that landed the first
          humans on the Moon."
        - "Concorde was an Anglo-French turbojet-powered supersonic
          passenger airliner."

    This frame is deliberately **language-agnostic** and contains no surface
    strings beyond neutral lemmas. All language-specific realization happens
    downstream (lexicon + constructions + family engines).

    Core conventions
    ----------------
    * The vehicle being described is always `main_entity`.
    * Coarse type information is recorded in `vehicle_kind` and/or the
      `role_lemmas` list.
    * Technical details are stored in the `technical_specs` dictionary
      using conventional keys, rather than adding a separate top-level
      field for each possible parameter.

    Fields
    ------
    frame_type:
        Constant string identifier for this frame family: `"vehicle"`.
        Used for debugging and routing.

    main_entity:
        The vehicle, craft, or rolling stock the article / summary is about.
        Typically an `Entity` with `entity_type` set to something like:
        `"ship"`, `"aircraft"`, `"locomotive"`, `"spacecraft"`, etc.

    vehicle_kind:
        Optional coarse type label for the vehicle, e.g.:
            - "ship"
            - "submarine"
            - "boat"
            - "aircraft"
            - "helicopter"
            - "airliner"
            - "fighter_aircraft"
            - "locomotive"
            - "multiple_unit"
            - "railcar"
            - "tank"
            - "car"
            - "spacecraft"
            - "satellite"
        Left as a free string so projects can define their own inventory.
        Often mirrors or refines `main_entity.entity_type`.

    class_designation:
        Optional `Entity` for the class or series the vehicle belongs to,
        e.g. a ship class, aircraft type, locomotive class. This allows
        sentences like "X is a Y-class destroyer".

    series_name:
        Optional neutral lemma describing the series or class name when
        treating it as a label rather than an entity (e.g. "type_45",
        "boeing_747"). Downstream, the lexicon can realize human-friendly
        names from this value.

    manufacturer:
        `Entity` representing the main manufacturer, builder, or constructor
        (e.g. "Boeing", "Harland and Wolff"). May be `None` when unknown.

    builders:
        List of `Entity` objects for builders / shipyards / factories
        responsible for this particular unit, if more detailed information
        is available.

    operators:
        List of `Entity` objects that operate or have operated the vehicle,
        such as navies, air forces, airlines, railway companies, or space
        agencies. This supports sentences like:
        "She was operated by the Royal Navy and later the Hellenic Navy."

    registration_identifiers:
        Tail numbers, pennant numbers, registration marks, hull numbers,
        or similar identifiers, in canonical string form. Example:
            ["G-BOAC"], ["S102"], ["OV-102"].

    home_port_or_base:
        Home port, air base, depot, or similar. Represented as a `Location`
        so it can be reused as a place entity elsewhere. May be `None`.

    role_lemmas:
        Neutral lemmas describing the primary role(s) or function(s) of the
        vehicle, e.g.:
            ["destroyer"], ["fighter"], ["airliner"],
            ["research_vessel"], ["cargo_ship"].
        These are not inflected strings; they are keys for lexicon lookup.

    status_lemmas:
        Lemmas describing the current / final status, e.g.:
            ["in_service"], ["retired"], ["scrapped"], ["museum_ship"].

    construction_timespan:
        `TimeSpan` covering the design/build period, if known.

    launch_timespan:
        `TimeSpan` for launch / first flight / rollout, depending on
        vehicle type.

    service_entry:
        `TimeSpan` for entry into service or commissioning.

    service_end:
        `TimeSpan` for withdrawal from service, decommissioning, or similar.

    loss_or_disposition_timespan:
        `TimeSpan` for sinking, crash, scrapping, or final disposition,
        when distinct from `service_end`.

    primary_theater_locations:
        Optional list of `Location` objects indicating theaters of
        operation (e.g. "North Atlantic", "Pacific Ocean", "Western Front").
        This is deliberately coarse; detailed campaigns should use event
        frames.

    technical_specs:
        Free-form dictionary for technical parameters that might or might
        not be verbalized. Typical numeric keys include (conventions only):

            {
                "length_m": 70.5,
                "wingspan_m": 35.8,
                "height_m": 12.3,
                "displacement_t": 18000.0,
                "maximum_takeoff_mass_kg": 250000,
                "powerplant_description": "2 x turbojet",
                "maximum_speed_kmh": 2200,
                "cruise_speed_kmh": 900,
                "range_km": 12000,
                "crew": 12,
                "passenger_capacity": 120,
            }

        Units should be encoded in the key names (e.g. `_m`, `_kmh`,
        `_t`) to avoid ambiguity.

    attributes:
        Additional, structured properties that do not justify their own
        field or are rarely used. Examples:

            {
                "imo_number": "1234567",
                "icao_type_designator": "B744",
                "faa_designation": "B-52H",
                "registration_country_lemma": "united_states",
            }

    extra:
        Arbitrary metadata, typically used for provenance or storing the
        original source representation. Examples:

            {
                "wikidata_qid": "Q12345",
                "aw_raw": {...},   # original Abstract Wikipedia / Ninai frame
                "notes": "merged from multiple sources"
            }

        This field should not affect semantics directly; it is mainly for
        debugging, round-tripping, and translation back to upstream schemas.
    """

    # Constant family identifier; not included in __init__.
    frame_type: ClassVar[str] = "vehicle"

    # Core identity
    main_entity: Entity

    # Classification and series
    vehicle_kind: Optional[str] = None
    class_designation: Optional[Entity] = None
    series_name: Optional[str] = None

    # Industrial relations
    manufacturer: Optional[Entity] = None
    builders: List[Entity] = field(default_factory=list)
    operators: List[Entity] = field(default_factory=list)

    # Identification / base
    registration_identifiers: List[str] = field(default_factory=list)
    home_port_or_base: Optional[Location] = None

    # Roles and status
    role_lemmas: List[str] = field(default_factory=list)
    status_lemmas: List[str] = field(default_factory=list)

    # Temporal lifecycle
    construction_timespan: Optional[TimeSpan] = None
    launch_timespan: Optional[TimeSpan] = None
    service_entry: Optional[TimeSpan] = None
    service_end: Optional[TimeSpan] = None
    loss_or_disposition_timespan: Optional[TimeSpan] = None

    # Operational theaters
    primary_theater_locations: List[Location] = field(default_factory=list)

    # Technical and miscellaneous attributes
    technical_specs: Dict[str, Any] = field(default_factory=dict)
    attributes: Dict[str, Any] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)


__all__ = ["VehicleFrame"]
