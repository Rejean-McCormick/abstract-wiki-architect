# semantics\entity\geopolitical_entity_frame.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, List, Optional

from semantics.types import Entity, Location, TimeSpan


@dataclass
class GeopoliticalEntityFrame:
    """
    Geopolitical entity frame.

    High-level semantic frame for Wikipedia-style summaries of **countries,
    regions, cities, municipalities, and other administrative units**.

    The goal is to capture enough structure to support sentences such as:

        - "France is a country in Western Europe."
        - "Munich is the capital and most populous city of Bavaria in Germany."
        - "Greenland is an autonomous territory within the Kingdom of Denmark."

    This frame is deliberately **language-agnostic** and contains no surface
    strings beyond neutral lemmas. All language-specific realization happens
    downstream (lexicon + constructions + family engines).

    Core conventions
    ----------------
    * The entity being described is always `main_entity`.
    * Administrative type / level is modeled via `geo_kind` and/or
      `attributes["admin_level"]`.
    * Parent–child administrative relations use `parent_entities`.
    * Highly domain-specific or rarely used information should go into
      `attributes` / `extra` rather than gaining its own top-level field.

    Fields
    ------
    frame_type:
        Constant string identifier for this frame family: `"geopolitical-entity"`.
        Used for debugging and (optionally) routing.

    main_entity:
        The geopolitical entity the article / summary is about.
        Typically an `Entity` with `entity_type` set to something like:
        `"country"`, `"city"`, `"province"`, `"region"`, etc.

    geo_kind:
        Optional coarse type label for the entity, e.g.:
            - "country"
            - "sovereign_state"
            - "autonomous_territory"
            - "constituent_country"
            - "federal_state"
            - "province"
            - "region"
            - "county"
            - "municipality"
            - "city"
            - "town"
        Left as a free string so projects can define their own inventory.
        This often mirrors or refines `main_entity.entity_type`.

    parent_entities:
        Administrative containers of `main_entity`, ordered from *closest*
        to *broadest*. Examples:

            - For a city: [state, country]
            - For a state: [country]
            - For a country: [continent_or_region] (optional)

        Each parent is represented as an `Entity` so it can be reused in
        other frames and realized via the lexicon.

    parent_locations:
        Optional list of `Location` objects mirroring / supplementing
        `parent_entities` when you have richer location-oriented metadata
        (e.g. specific regions, macroregions, statistical areas).
        For many pipelines this can be left empty and `parent_entities`
        will be sufficient.

    capital:
        Capital city, if applicable (e.g. for a country, state or region).
        Represented as a `Location`. May be `None` for entities where
        the notion of a capital does not apply.

    seat_of_government:
        Seat of government when it differs from `capital` (e.g. some
        countries or regions with split capitals). If it is the same
        as `capital`, you may either leave this as `None` or repeat it,
        depending on how explicit you want the semantics to be.

    largest_city:
        Largest city by population, if this is not (or not guaranteed to be)
        the same as `capital`. Optional; may be `None`.

    population:
        Total population count (typically an integer). The exact unit is
        "number of inhabitants".

    population_timespan:
        `TimeSpan` indicating when `population` is measured, usually with
        just `start_year` set (e.g. census year). For example:
            TimeSpan(start_year=2020) for "as of 2020".

    area_km2:
        Total area in square kilometres, as a float. If your source data
        uses other units (e.g. square miles), normalize it before populating
        this field, and store the original unit/value in `attributes` or
        `extra` if needed.

    inception:
        `TimeSpan` for when the geopolitical entity was created or
        formally established (e.g. independence date, creation of a
        municipality). Can be approximate.

    dissolution:
        `TimeSpan` for when the entity ceased to exist (if it is historical).
        Typically `None` for current entities.

    official_language_lemmas:
        Neutral lemmas identifying the official language(s), e.g.:
            ["english"], ["french", "german", "italian"].
        These are language-agnostic keys that the lexicon layer will map
        to actual lexemes per output language. For more complex setups
        you can instead store full `Entity` objects in `attributes`.

    demonym_lemmas:
        Lemmas for adjectival or nominal demonyms associated with
        the entity, e.g. ["french"], ["polish"]. The lexicon can then
        realize gender/number-marked forms as needed.

    government_type_lemmas:
        Lemmas describing the form of government or administrative status,
        e.g.:
            ["unitary", "parliamentary", "republic"]
            ["federal", "semi_presidential", "republic"]

        Downstream, these can be combined into phrases like
        "a federal semi-presidential republic".

    memberships:
        List of `Entity` objects representing supranational or regional
        organizations the entity belongs to, e.g.:
            - United Nations
            - European Union
            - African Union
            - Schengen Area
        These can feed sentences such as "France is a member of the
        European Union and the Schengen Area."

    attributes:
        Free-form attribute map for additional, structured properties that
        do not justify dedicated fields. Examples (keys are conventions,
        not enforced):

            {
                "iso_3166_1_alpha2": "FR",
                "iso_3166_1_alpha3": "FRA",
                "continent_lemmas": ["europe"],
                "subregion_lemmas": ["western_europe"],
                "elevation_m": 35.0,
                "time_zones": ["UTC+1", "UTC+2 (DST)"],
            }

        Use this for any domain-specific detail that may or may not be
        realized in surface text.

    extra:
        Arbitrary metadata, typically used for provenance or storing the
        original source representation. Examples:

            {
                "wikidata_qid": "Q142",
                "aw_raw": {...},   # original Abstract Wikipedia / Ninai frame
                "notes": "merged from multiple sources"
            }

        This field should not affect semantics directly; it is mainly for
        debugging, round-tripping, and translation back to upstream schemas.
    """

    # Constant family identifier; not included in __init__.
    frame_type: ClassVar[str] = "geopolitical-entity"

    # Core identity
    main_entity: Entity

    # Classification / administrative role
    geo_kind: Optional[str] = None

    # Containment hierarchy
    parent_entities: List[Entity] = field(default_factory=list)
    parent_locations: List[Location] = field(default_factory=list)

    # Key places associated with the entity
    capital: Optional[Location] = None
    seat_of_government: Optional[Location] = None
    largest_city: Optional[Location] = None

    # Quantitative facts
    population: Optional[int] = None
    population_timespan: Optional[TimeSpan] = None
    area_km2: Optional[float] = None

    # Temporal existence
    inception: Optional[TimeSpan] = None
    dissolution: Optional[TimeSpan] = None

    # Linguistic / political descriptors
    official_language_lemmas: List[str] = field(default_factory=list)
    demonym_lemmas: List[str] = field(default_factory=list)
    government_type_lemmas: List[str] = field(default_factory=list)

    # Memberships in organizations / unions
    memberships: List[Entity] = field(default_factory=list)

    # Generic extension points
    attributes: Dict[str, Any] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)


__all__ = ["GeopoliticalEntityFrame"]
