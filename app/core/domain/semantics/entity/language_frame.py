# semantics\entity\language_frame.py
"""
semantics/entity/language_frame.py
----------------------------------

Semantic frame for *languages* and closely related varieties.

This frame covers natural languages, constructed languages, sign
languages, and well-defined dialects or macrolanguage members.

The frame is intentionally language-neutral: all surface realization is
handled later by the NLG layer (lexicon, morphology, constructions).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from semantics.types import Entity, Event, Location, TimeSpan


@dataclass
class LanguageFrame:
    """
    High-level frame for languages and language varieties.

    Typical examples:
        - A natural language (“French”, “Swahili”)
        - A constructed language (“Esperanto”)
        - A sign language (“American Sign Language”)
        - A dialect / variety of another language

    Fields
    ------

    frame_type:
        Constant identifying this family of frames. Used by routers
        and engines to dispatch to the right realization logic.

    main_entity:
        The language entity itself (e.g. “English”, “Hindi”).

    language_type:
        Coarse type label, e.g. "natural", "constructed",
        "sign", "mixed", "creole", "pidgin". Left as a free string
        so projects can choose their own inventory.

    family_lemmas:
        Lemmas for the genealogical family, e.g.
        ["indoeuropean"], ["bantu"], ["austronesian"].

    branch_lemmas:
        Lemmas for sub-family / branch classification, e.g.
        ["germanic"], ["romance"], ["slavic"].

    parent_language:
        Optional parent / macrolanguage entity for dialects or
        standardized varieties.

    ancestor_languages:
        List of entities representing important historical ancestors
        (e.g. “Latin” for Romance languages).

    child_languages:
        List of entities representing direct descendants or major
        varieties/dialects.

    iso_639_1, iso_639_2, iso_639_3:
        ISO 639 codes, when applicable.

    glottocode:
        Optional Glottolog code.

    regions:
        List of locations where the language is spoken; these can be
        countries, regions, or more fine-grained areas.

    countries:
        List of entities representing countries where the language
        has notable presence (spoken or official).

    speakers_estimate:
        Approximate number of speakers (typically L1 + L2) as an
        integer, if such an aggregate is available.

    speakers_timespan:
        Time span describing when `speakers_estimate` applies, e.g.
        a census year.

    speakers_source:
        Optional short label / citation hint for the speaker numbers,
        e.g. "Ethnologue 2023".

    script_lemmas:
        Lemmas for scripts used to write the language, e.g.
        ["latin"], ["cyrillic"], ["devanagari"].

    writing_system_lemmas:
        Lemmas for more specific writing systems, if needed, e.g.
        ["traditional chinese"], ["simplified chinese"].

    official_statuses:
        Mapping from a country/entity identifier (or name) to a
        status string, e.g.:
            {
                "Q142": "official",
                "Q183": "minority",
                "Q38": "co-official"
            }

    regulatory_bodies:
        List of entities representing language academies or regulatory
        institutions (e.g. “Académie française”).

    standardization_events:
        Events describing codification, orthographic reforms, or other
        major standardization milestones.

    other_names:
        List of alternate names / autonyms / exonyms, without strong
        subtype distinctions.

    endonym:
        Primary self-designation of the language (e.g. “Deutsch”).

    exonyms:
        Common external names (e.g. “German”, “Alemán”).

    attributes:
        Arbitrary attribute map of additional, language-specific
        information (e.g. "word_order", "morphological_type",
        "language_status", "language_family_id").

    extra:
        Opaque metadata bag for passing through original source
        structures (e.g. raw JSON, Wikidata statements, AW records).
    """

    frame_type: str = "language"
    main_entity: Entity = field(default_factory=Entity)

    language_type: Optional[str] = None

    family_lemmas: List[str] = field(default_factory=list)
    branch_lemmas: List[str] = field(default_factory=list)

    parent_language: Optional[Entity] = None
    ancestor_languages: List[Entity] = field(default_factory=list)
    child_languages: List[Entity] = field(default_factory=list)

    iso_639_1: Optional[str] = None
    iso_639_2: Optional[str] = None
    iso_639_3: Optional[str] = None
    glottocode: Optional[str] = None

    regions: List[Location] = field(default_factory=list)
    countries: List[Entity] = field(default_factory=list)

    speakers_estimate: Optional[int] = None
    speakers_timespan: Optional[TimeSpan] = None
    speakers_source: Optional[str] = None

    script_lemmas: List[str] = field(default_factory=list)
    writing_system_lemmas: List[str] = field(default_factory=list)

    official_statuses: Dict[str, str] = field(default_factory=dict)
    regulatory_bodies: List[Entity] = field(default_factory=list)

    standardization_events: List[Event] = field(default_factory=list)

    other_names: List[str] = field(default_factory=list)
    endonym: Optional[str] = None
    exonyms: List[str] = field(default_factory=list)

    attributes: Dict[str, Any] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)


__all__ = ["LanguageFrame"]
