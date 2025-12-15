# semantics\entity\artifact_frame.py
"""
semantics/entity/artifact_frame.py
----------------------------------

Semantic frame for *artifacts* / *physical objects*.

This frame covers individual man-made objects (or well-defined classes of
objects) such as tools, weapons, machines, instruments, artworks,
vehicles, and other physical artifacts.

The frame is intentionally language-neutral: all surface realization is
handled later by the NLG layer (lexicon, morphology, constructions).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from semantics.types import Entity, Event, Location, TimeSpan


@dataclass
class ArtifactFrame:
    """
    High-level frame for physical artifacts.

    Typical examples:
        - A specific sword
        - A particular camera model
        - A famous statue
        - A historical machine

    The frame is designed to be flexible enough to handle both
    single, concrete objects and named models/series.

    Fields
    ------

    frame_type:
        Constant identifying this family of frames. Used by routers
        and engines to dispatch to the right realization logic.

    main_entity:
        The artifact entity itself (e.g. “Eiffel Tower”, “Hubble Space Telescope”).

    artifact_type_lemmas:
        Lemmas describing the type/category of artifact, e.g.
        ["tower"], ["telescope"], ["bridge"].
        These are language-neutral; the realization layer chooses the
        correct lexeme and inflection for the target language.

    makers:
        List of entities that *made* or *designed* the artifact,
        e.g. engineers, artists, manufacturers.

    owners:
        List of entities currently owning or historically owning
        the artifact (e.g. museums, companies, private owners).

    current_location:
        Where the artifact is currently located (or most relevantly
        associated), e.g. a museum, city, or region.

    creation_event:
        Optional event describing when/how the artifact was created,
        built, launched, forged, etc.

    production_timespan:
        Optional time span covering construction/production dates for
        the artifact (start/end years, etc.).

    materials_lemmas:
        Lemmas describing the main materials, e.g. ["steel"], ["bronze"],
        ["wood"], ["concrete"].

    function_lemmas:
        Lemmas describing the primary function or use, e.g.
        ["observation"], ["transport"], ["communication"].

    dimensions:
        Structured dimensional information, if available, for example:
            {
                "height_m": 324.0,
                "length_m": 50.0,
                "mass_kg": 12000.0,
                "diameter_m": 3.0,
            }
        Keys are not enforced here; normalization code is responsible
        for choosing a consistent schema.

    heritage_designations:
        Optional list of heritage/protection designations, e.g.
        ["UNESCO World Heritage Site", "National Monument"].

    attributes:
        Arbitrary attribute map of additional, artifact-specific
        information (e.g. "style", "model_year", "serial_number").

    extra:
        Opaque metadata bag for passing through original source
        structures (e.g. raw JSON, Wikidata statements, etc.).
    """

    frame_type: str = "artifact"
    main_entity: Entity = field(default_factory=Entity)

    artifact_type_lemmas: List[str] = field(default_factory=list)
    makers: List[Entity] = field(default_factory=list)
    owners: List[Entity] = field(default_factory=list)

    current_location: Optional[Location] = None
    creation_event: Optional[Event] = None
    production_timespan: Optional[TimeSpan] = None

    materials_lemmas: List[str] = field(default_factory=list)
    function_lemmas: List[str] = field(default_factory=list)

    dimensions: Dict[str, Any] = field(default_factory=dict)
    heritage_designations: List[str] = field(default_factory=list)

    attributes: Dict[str, Any] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)


__all__ = ["ArtifactFrame"]
