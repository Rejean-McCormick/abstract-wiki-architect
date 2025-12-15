# semantics\entity\place_frame.py
# semantics/entity/place_frame.py

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from semantics.types import Entity, Location, TimeSpan


@dataclass
class PlaceFrame:
    """
    High-level semantic frame for geographic / place entities.

    This frame is intended for first-sentence / short-intro summaries of:
        - Geopolitical units (countries, regions, cities, municipalities…)
        - Natural geographic features (mountains, rivers, lakes, islands, parks…)
        - Built facilities / infrastructure (buildings, airports, stations, stadiums…)

    It is structurally parallel to BioFrame but specialized for places instead of
    persons. The goal is to give the NLG layer enough structure to choose between
    equatives, locatives, appositions, and other constructions.

    Fields
    ------
    frame_type:
        Stable discriminator for routing and introspection. Always "place".

    main_entity:
        The underlying entity that the article or sentence is about.
        For example:
            - a country entity,
            - a city entity,
            - a specific building entity.

        Typically this is the entity corresponding to the page / item in the
        upstream knowledge base (e.g. Wikidata item for "Paris").

    primary_kind:
        Coarse semantic kind / type label for the place, such as:
            - "country", "sovereign_state"
            - "city", "town", "village", "municipality"
            - "region", "province", "state", "county"
            - "mountain", "river", "lake", "island", "park"
            - "building", "airport", "railway_station", "stadium", "bridge"
        This is a free string but should preferably come from a small
        controlled inventory used across the project.

    locations:
        Optional explicit location hierarchy for where the place is situated.
        Each `Location` can represent a containing unit such as:
            - region,
            - state / province,
            - country,
            - continent.

        The list is typically ordered from the most specific container to the
        most general (e.g. [region, country, continent]), but this is not
        strictly enforced.

    admin_level:
        Optional administrative level for geopolitical units, represented as a
        small integer (e.g. 1 = country, 2 = first-level subdivision, 3 = second-
        level subdivision, 4 = municipality). For non-administrative natural
        features, this is usually left as None.

    timespan:
        Optional `TimeSpan` describing the existence of the place as a defined
        entity. Useful for historical entities that were created, merged, or
        abolished (e.g. former provinces, historical countries).

    population:
        Optional integer population for the place at the reference time.
        For example, a city's or country's population.

    population_timespan:
        Optional `TimeSpan` indicating when the `population` value applies
        (e.g. census year). When only a year is known, populate
        `population_timespan.start_year`.

    area_km2:
        Optional surface area in square kilometres.

    elevation_m:
        Optional elevation above sea level in metres.
        For example, average elevation of a city or elevation of a mountain peak.

    parent_entities:
        Optional list of parent entities that this place is part of or subordinate
        to, in a more general sense than purely geographic containment. Examples:
            - For a capital city: the country entity it is capital of.
            - For a stadium: the club or organization that owns or operates it.

        This is a generic hook for "X is part of / belongs to Y" relationships
        that are useful in intros.

    attributes:
        Free-form attribute map for additional structured facts about the place.
        Examples (keys are project conventions, not enforced by the type):

            {
                "capital_of": [Entity(...), ...],
                "languages": ["english", "french"],
                "climate": "humid_subtropical",
                "function": ["airport", "hub_for_airline_X"],
                "located_on": ["river", "coast"],
            }

        The NLG layer can interpret certain attributes (like "capital_of" or
        "languages") to choose richer constructions, while unknown attributes
        are simply ignored.

    extra:
        Arbitrary metadata preserved from upstream systems (e.g. original JSON
        from Abstract Wikipedia, Wikidata IDs, or AW-internal structures).
        This is not interpreted by the NLG layer but kept for traceability and
        debugging.
    """

    frame_type: str = "place"

    main_entity: Optional[Entity] = None
    primary_kind: Optional[str] = None

    locations: List[Location] = field(default_factory=list)
    admin_level: Optional[int] = None
    timespan: Optional[TimeSpan] = None

    population: Optional[int] = None
    population_timespan: Optional[TimeSpan] = None
    area_km2: Optional[float] = None
    elevation_m: Optional[float] = None

    parent_entities: List[Entity] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)


__all__ = ["PlaceFrame"]
