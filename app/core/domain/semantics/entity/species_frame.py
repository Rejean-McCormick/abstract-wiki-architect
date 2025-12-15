# semantics\entity\species_frame.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from semantics.types import Entity, Event, Location, TimeSpan


@dataclass
class SpeciesFrame:
    """
    Semantic frame for a biological taxon (typically a species) summary.

    This frame is intended to support Wikipedia-style lead sentences such as:

        - "Panthera leo is a species of big cat in the family Felidae."
        - "Quercus robur is a species of flowering plant in the beech family Fagaceae."
        - "Ailuropoda melanoleuca is an endangered species of bear endemic to China."

    The frame is used as an input to the NLG system; it does not perform any
    rendering by itself.

    Fields
    ------
    main_taxon:
        The focal taxon entity (species, genus, family, etc.).
        Typically an Entity with `entity_type="taxon"` and a canonical name.
    rank:
        Taxonomic rank label ("species", "genus", "family", "order", ...).
        Defaults to "species".
    scientific_name:
        Canonical scientific name in binomial/trinomial form, e.g. "Panthera leo".
        Optional but strongly recommended.
    common_names:
        List of localized common names for this taxon.
        These are plain strings in the output language (if known), or language-
        neutral labels otherwise.
    higher_taxa:
        Mapping `rank -> Entity` for container taxa, e.g.:

            {
                "genus": Entity(name="Panthera", entity_type="taxon"),
                "family": Entity(name="Felidae", entity_type="taxon"),
            }

        This keeps the representation flexible for different rank systems.
    parent_taxon:
        Convenience alias for the immediate parent taxon (usually the genus).
        It should also appear in `higher_taxa` under the appropriate rank key.
    fossil_range:
        Optional TimeSpan representing geological or fossil range, where
        applicable (e.g. for extinct taxa).
        Can also be used as a coarse "known since" / "described in" range.
    description_event:
        Optional Event describing the formal description / naming of the taxon
        (e.g. who described it, in which year, where).
    distribution:
        List of Location objects representing native / natural range, endemic
        regions, or typical occurrence.
    habitat_lemmas:
        Language-neutral lemmas for the typical habitat(s), e.g.
        ["forest", "savanna", "freshwater", "marine"].
        The realization layer is responsible for mapping these to lexemes in
        the target language.
    conservation_status:
        Human-readable conservation category, e.g. "LC", "NT", "VU", "EN", "CR",
        or a fully spelled-out label such as "Least Concern".
    conservation_system:
        Name or identifier of the system used for `conservation_status`,
        e.g. "IUCN3.1", "ESA", or a project-specific code.
    population_trend:
        Qualitative population trend, e.g. "increasing", "stable", "decreasing".
    attributes:
        Arbitrary attribute map for additional biologically relevant properties,
        for example:

            {
                "diet": ["herbivore"],
                "body_mass_kg": 190,
                "nocturnal": True,
                "trophic_level": "apex",
            }

        Keys are free-form strings; values can be any JSON-serializable data.
    extra:
        Arbitrary metadata (e.g. Wikidata IDs, source JSON blobs, debug info).
        This is not interpreted by the NLG system but is preserved for callers.
    """

    # Top-level frame discriminator for routing; kept out of __init__ so callers
    # do not need to pass it explicitly.
    frame_type: str = field(init=False, default="species")

    # Core identity
    main_taxon: Entity
    rank: str = "species"
    scientific_name: str = ""

    # Names and taxonomic context
    common_names: List[str] = field(default_factory=list)
    higher_taxa: Dict[str, Entity] = field(default_factory=dict)
    parent_taxon: Optional[Entity] = None

    # Temporal and event information
    fossil_range: Optional[TimeSpan] = None
    description_event: Optional[Event] = None

    # Ecology and conservation
    distribution: List[Location] = field(default_factory=list)
    habitat_lemmas: List[str] = field(default_factory=list)
    conservation_status: Optional[str] = None
    conservation_system: Optional[str] = None
    population_trend: Optional[str] = None

    # Open-ended attributes and metadata
    attributes: Dict[str, Any] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)


__all__ = ["SpeciesFrame"]
