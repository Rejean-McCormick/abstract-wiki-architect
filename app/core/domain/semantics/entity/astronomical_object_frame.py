# semantics\entity\astronomical_object_frame.py
"""
semantics/entity/astronomical_object_frame.py
---------------------------------------------

High-level semantic frame for astronomical objects.

This module defines a small, typed data class that represents the
*meaning-level* input for Wikipedia-style sentences about astronomical
objects such as stars, planets, moons, galaxies, nebulae, exoplanets,
and minor planets.

The intention is similar to `BioFrame` in `semantics.types`: downstream
code (normalizers, AW/Z bridges, etc.) builds an `AstronomicalObjectFrame`
from loosely structured source data, and the NLG layer chooses suitable
constructions (equatives, attributives, appositives) to render
introductory sentences like:

    - "Proxima Centauri is a red dwarf star in the Alpha Centauri system."
    - "Kepler-22b is an exoplanet orbiting within the habitable zone of
       the Sun-like star Kepler-22."
    - "Andromeda is a barred spiral galaxy approximately 2.5 million
       light-years from the Milky Way."

The frame is deliberately modest: it exposes a few commonly useful
fields explicitly (class / kind, host system, parent body, distance,
discovery) and keeps everything else in structured dictionaries. This
keeps the core library light-weight while still being expressive enough
for templated rendering.

Typical usage
=============

    from semantics.types import Entity
    from semantics.entity.astronomical_object_frame import AstronomicalObjectFrame

    andromeda = Entity(
        id="Q2469",
        name="Andromeda Galaxy",
        entity_type="astronomical_object",
        extra={"wikidata_qid": "Q2469"},
    )

    milky_way = Entity(
        id="Q323",
        name="Milky Way",
        entity_type="astronomical_object",
    )

    frame = AstronomicalObjectFrame(
        main_entity=andromeda,
        object_kind_lemmas=["galaxy"],
        subtype_lemmas=["barred", "spiral"],
        host_system=milky_way,
        distance_ly=2_500_000.0,
        classification={
            "morphological_type": "SA(s)b",
        },
        physical_properties={
            "mass_solar": 1.230e12,
        },
    )

Downstream code can then pick appropriate constructions for a given
language, using:

    - `object_kind_lemmas` / `subtype_lemmas` to build the predicate NP,
    - `host_system` / `parent_body` to express orbital or containment
      relations,
    - `distance_ly` (or entries from `physical_properties`) to add
      quantitative details,
    - `discovery_*` fields / `events` for more specialized sentences.

This module is purely semantic and has no dependencies on engines,
morphology, or IO.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from semantics.types import Entity, Event, TimeSpan


@dataclass
class AstronomicalObjectFrame:
    """
    High-level semantic frame for an astronomical object.

    This frame is designed to support short encyclopedic descriptions of
    objects such as planets, moons, stars, galaxies, nebulae, exoplanets,
    comets, and minor planets.

    Fields
    ------

    main_entity:
        The entity the article / description is about, e.g. "Earth",
        "Proxima Centauri", "Andromeda Galaxy". This should be the
        canonical subject of the page.

    object_kind_lemmas:
        Language-neutral lemmas for the core object class, used to build
        phrases like "a dwarf planet", "a red dwarf star", "a spiral
        galaxy".

        Examples (English lemmas):

            ["planet"]
            ["dwarf", "planet"]
            ["star"]
            ["spiral", "galaxy"]
            ["exoplanet"]

        Realization code is expected to map these lemmas to lexicon
        entries per language.

    subtype_lemmas:
        Additional lemmas for fine-grained classification beyond the
        core kind, for example:

            - spectral class (e.g. ["red", "dwarf"])
            - morphological subtype (e.g. ["barred", "spiral"])
            - dynamical subtype (e.g. ["hot", "Jupiter"])

        These typically appear as modifiers around `object_kind_lemmas`
        (adjectives or compound nouns), but the exact phrasing is left
        to the language-specific renderer.

    host_system:
        Optional larger-scale system that the object belongs to, such as:

            - the galaxy containing a star system,
            - the star system containing an exoplanet,
            - the planetary system containing a moon.

        Examples:

            - Milky Way as host system for the Solar System (if you treat
              "Solar System" as the main_entity and "Milky Way" as host).
            - "Alpha Centauri system" as host for Proxima Centauri b.

        Renderers can use this in relative clauses ("in the Milky Way")
        or PPs ("in the Alpha Centauri system").

    parent_body:
        Immediate gravitational parent (if any), for example:

            - the star for a planet,
            - the planet for a natural satellite,
            - the galaxy for a globular cluster.

        This is distinct from `host_system` which can be more abstract
        or larger scale. A renderer may choose to generate clauses like
        "orbiting the Sun" or "orbiting the gas giant Jupiter" from this
        field.

    constellation:
        Optional entity representing the constellation or named region
        where the object is observed on the celestial sphere, e.g.
        "Orion", "Andromeda". Typically useful for stars and deep-sky
        objects.

    distance_ly:
        Approximate distance from Earth in light-years (if known). This
        is suitable for simple numeric renderings, e.g.:

            "approximately 2.5 million light-years from the Milky Way."

        If more elaborate or multi-unit representations are needed
        (parsecs, kilometers, AU), these should go into
        `physical_properties` or `attributes`.

    orbital_period_days:
        Orbital period in Earth days (for planets, moons, exoplanets,
        minor planets) if a single scalar value is sufficient. More
        detailed orbital parameters belong in `orbital_parameters`.

    discovery_time:
        Optional `TimeSpan` describing the date or approximate date of
        discovery. For historical objects this may be a specific year;
        for very old known objects it may be left `None`.

    discovery_agents:
        Optional list of entities representing discoverers or discovery
        teams (persons, observatories, missions), e.g. astronomers or
        survey projects. This is typically rendered in phrases like:

            "It was discovered in 1992 by Jane Doe and John Smith."

    discovery_event:
        Optional `Event` of type "discovery" describing the discovery as
        a full semantic event (participants, time, location, etc.). If
        present, it can be used by more advanced renderers that reason
        over generic `Event` structures instead of the more specialized
        `discovery_*` fields above.

    classification:
        Free-form dictionary for classification-related metadata that is
        too detailed or domain-specific to model as top-level fields,
        for example:

            {
                "spectral_type": "M5.5Ve",
                "harvard_class": "G2V",
                "hubble_type": "SA(s)b",
                "minor_planet_group": "Apollo",
                "iau_designation": "1995 QN",
            }

        This is purely semantic; renderers may cherry-pick what they
        know how to express.

    physical_properties:
        Free-form dictionary for physical parameters, typically numbers
        with units, for example:

            {
                "mass_kg": 1.989e30,
                "mass_solar": 1.0,
                "radius_km": 696_340,
                "mean_temperature_k": 5772,
                "absolute_magnitude": 4.83,
            }

        Where possible, callers should be consistent about keys and
        units (e.g. `_kg`, `_km`, `_au` suffixes).

    orbital_parameters:
        Free-form dictionary for orbital characteristics, e.g.:

            {
                "semi_major_axis_au": 1.0,
                "eccentricity": 0.0167,
                "inclination_deg": 7.155,
                "argument_of_periapsis_deg": 114.20783,
            }

        Again, choice of keys is left to the caller; the NLG layer can
        implement project-specific conventions.

    events:
        Optional list of other salient events involving the object,
        such as major observation campaigns, missions, collisions, or
        status changes. These are generic `Event` instances and can be
        used for multi-sentence narratives beyond the lead.

    attributes:
        Arbitrary attribute map for the main entity, similar to
        `BioFrame.attributes`. This is a good place to record things
        like:

            {
                "known_for": ["closest known exoplanet"],
                "designation": ["Alpha Centauri C", "HIP 70890"],
            }

        The keys are project-specific; the NLG layer should treat this
        as a flexible, optional bag of facts.

    extra:
        Arbitrary metadata, e.g. original JSON from an upstream
        knowledge graph, Wikidata IDs, or debug information. This field
        is not intended for direct realization.

    frame_type:
        Stable identifier for this frame family. This allows routing
        logic (e.g. in `nlg.api` or a future `router.render_*`) to
        distinguish `AstronomicalObjectFrame` from other frame types.

        For this class, the value is always:

            "astronomical_object"
    """

    # Core subject --------------------------------------------------------------
    main_entity: Entity

    # Classification / type information ----------------------------------------
    object_kind_lemmas: List[str] = field(default_factory=list)
    subtype_lemmas: List[str] = field(default_factory=list)

    host_system: Optional[Entity] = None
    parent_body: Optional[Entity] = None
    constellation: Optional[Entity] = None

    # Quantitative descriptors --------------------------------------------------
    distance_ly: Optional[float] = None
    orbital_period_days: Optional[float] = None

    # Discovery and history -----------------------------------------------------
    discovery_time: Optional[TimeSpan] = None
    discovery_agents: List[Entity] = field(default_factory=list)
    discovery_event: Optional[Event] = None

    # Richer structured metadata -----------------------------------------------
    classification: Dict[str, Any] = field(default_factory=dict)
    physical_properties: Dict[str, Any] = field(default_factory=dict)
    orbital_parameters: Dict[str, Any] = field(default_factory=dict)

    events: List[Event] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)

    # Frame routing identifier --------------------------------------------------
    frame_type: str = "astronomical_object"


__all__ = ["AstronomicalObjectFrame"]
