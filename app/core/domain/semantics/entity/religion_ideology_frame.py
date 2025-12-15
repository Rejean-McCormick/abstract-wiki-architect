# semantics\entity\religion_ideology_frame.py
"""
semantics/entity/religion_ideology_frame.py
------------------------------------------

High-level semantic frame for religions, belief systems, and ideologies.

This module defines a structured, language-independent representation for
Wikipedia-style summaries of:

    - Religions (e.g. Buddhism, Islam, Shinto)
    - Denominations / branches (e.g. Roman Catholicism, Sunni Islam)
    - Philosophical systems (e.g. Stoicism)
    - Political ideologies (e.g. liberalism, Marxism)

The frame is intentionally coarse and flexible. Higher-level pipelines
(AW/Ninai bridges, CSV readers, etc.) are expected to normalize their
input into this structure before passing it into routing / NLG engines.

Design principles
=================

- Keep *semantics only* here (no language-specific morphology).
- Prefer typed fields for common encyclopedic facts (classification,
  origin, founders, scriptures, adherents, branches).
- Provide a generic `attributes` / `extra` bag for everything else.

Example usage
=============

    from semantics.types import Entity, Location, Event
    from semantics.entity.religion_ideology_frame import ReligionIdeologyFrame

    christianity = Entity(id="Q5043", name="Christianity", entity_type="religion")

    frame = ReligionIdeologyFrame(
        main_entity=christianity,
        classification_lemmas=["religion"],
        tradition_family_lemmas=["Abrahamic"],
        origin_location=Location(id="L1", name="Levant", kind="region"),
        origin_event=Event(
            id="E1",
            event_type="emergence",
            time=TimeSpan(start_year=1, approximate=True),
        ),
        founder_entities=[
            Entity(id="Q302", name="Jesus", entity_type="person", human=True),
        ],
        primary_text_entities=[
            Entity(id="Q1845", name="Bible", entity_type="work"),
        ],
        estimated_adherents=2300000000,
        adherent_estimate_year=2020,
        key_belief_lemmas=["monotheism", "salvation", "resurrection"],
        key_practice_lemmas=["prayer", "worship", "sacraments"],
    )

Downstream components can use these fields to choose constructions such
as:

    - "X is an Abrahamic religion based on the life and teachings of Y."
    - "X is a political ideology that emphasizes Y."

"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from semantics.types import Entity, Event, Location


@dataclass
class ReligionIdeologyFrame:
    """
    Semantic frame for religions, denominations, belief systems, and ideologies.

    The goal is to support short, information-dense summaries such as
    typical first sentences in encyclopedic articles, while remaining
    flexible enough to handle a wide variety of subtypes (religious,
    philosophical, political, etc.).

    Core identity
    -------------

    main_entity:
        The religion / belief system / ideology itself, represented as
        an `Entity`. For example, an entity with:

            - name="Buddhism", entity_type="religion"
            - name="Liberalism", entity_type="ideology"

    frame_type:
        Stable label for routing / planning. For this frame we use
        "religion-ideology" so that it is clearly distinct from
        biography ("bio") and other entity frames.

    classification_lemmas:
        Lemmas describing the broad class of the system, such as:

            ["religion"]
            ["Abrahamic religion"]
            ["political ideology"]
            ["philosophical system"]

        These are language-neutral lemma keys that a lexicon or engine
        can map to concrete surface forms per language.

    tradition_family_lemmas:
        Higher-level tradition / family labels, e.g.:

            ["Abrahamic"]
            ["Dharmic"]
            ["Christian"]
            ["Marxist"]

        Useful for patterns like "X is an Abrahamic religion".

    Origin and history
    ------------------

    origin_location:
        Optional `Location` representing where the system originated
        (e.g. "Indian subcontinent", "Paris", "Athens").

    origin_event:
        Optional `Event` describing the emergence or founding, if you
        want a more structured representation (with time span, place,
        participants). Typical event_type values might be:

            "emergence", "founding", "codification"

    founder_entities:
        List of `Entity` objects representing key founders or origin
        figures (e.g. "Gautama Buddha", "Karl Marx", "Confucius").
        These can be used to build phrases like "founded by X" or
        "based on the teachings of X".

    core_figures:
        List of `Entity` objects representing central divine or
        emblematic figures, distinct from historical founders when
        needed. Examples:

            - deities (e.g. "Vishnu")
            - prophets (e.g. "Muhammad")
            - central personifications (e.g. "Liberty" in some contexts)

        Engines can decide whether and how to mention these (often
        omitted in very short summaries).

    Doctrine, practices, and texts
    ------------------------------

    key_belief_lemmas:
        List of lemma-like labels for core beliefs and themes, e.g.:

            ["monotheism", "nonviolence", "class struggle"]

        Intended for templates like "which emphasizes X and Y".

    key_practice_lemmas:
        List of lemma-like labels for characteristic practices, e.g.:

            ["prayer", "meditation", "sacraments", "pilgrimage"]

    primary_text_entities:
        List of `Entity` objects representing scriptures or canonical
        texts (e.g. "Bible", "Qur'an", "Communist Manifesto").

        These entities should usually have entity_type="work" or a
        similar hint, but this is not enforced.

    institutional_entities:
        List of `Entity` objects representing major institutions or
        organizations associated with this system, such as:

            - "Catholic Church"
            - "World Council of Churches"
            - "Communist Party of China"

        This is mainly useful for longer descriptions; short
        first-sentence bios typically omit them, but they are kept here
        for completeness.

    Demographics and spread
    -----------------------

    geographic_scope:
        List of `Location` objects representing main regions where the
        system is practiced or influential ("worldwide", "South Asia",
        "Europe and the Americas", etc.). For very short texts, engines
        might collapse this into a simpler phrase.

    estimated_adherents:
        Optional approximate number of adherents / followers, as an
        integer. For example, 1400000000 for 1.4 billion.

        This is deliberately untyped; use whatever convention fits your
        data (e.g. rounded to the nearest million).

    adherent_estimate_year:
        Optional year for which the adherent estimate is intended (e.g.
        2020). If provided, engines may choose to mention the year in
        more detailed summaries.

    Relationships and variants
    --------------------------

    parent_traditions:
        List of `Entity` objects representing conceptual or historical
        parents / sources, e.g.:

            - Hellenistic religion as a parent of certain sects
            - "Classical liberalism" as a parent of "social liberalism"

    derived_traditions:
        List of `Entity` objects representing direct offshoots,
        denominations, or derived ideologies (e.g. "Mahayana" as a
        derived tradition from early Buddhism).

    branches:
        List of `Entity` objects representing major internal branches /
        denominations. Unlike `derived_traditions`, these are typically
        considered part of the same umbrella system, e.g.:

            - "Sunni Islam", "Shia Islam"
            - "Theravada", "Mahayana", "Vajrayana"

        Some pipelines may choose to encode branches in
        `derived_traditions` instead; both are provided to give
        flexibility.

    Generic extension points
    ------------------------

    attributes:
        Arbitrary attribute map for structured data that does not
        justify a dedicated top-level field, for example:

            {
                "sacred_languages": ["latin", "sanskrit"],
                "organizational_structure": "decentralized",
                "main_ritual_yearly_festivals": ["Easter", "Christmas"]
            }

        Keys are free-form strings; values are expected to be JSON-like
        (str, int, float, list, dict).

    extra:
        Opaque metadata bag for pipeline-specific information, such as
        original JSON, Wikidata IDs, provenance, etc. This is not
        intended to be interpreted by language-independent NLG logic.

    """

    #: Stable type label used by router / planners
    frame_type: str = "religion-ideology"

    #: The religion / belief system / ideology being described.
    main_entity: Entity = field(default_factory=Entity)

    # Core classification
    classification_lemmas: List[str] = field(default_factory=list)
    tradition_family_lemmas: List[str] = field(default_factory=list)

    # Origin
    origin_location: Optional[Location] = None
    origin_event: Optional[Event] = None
    founder_entities: List[Entity] = field(default_factory=list)
    core_figures: List[Entity] = field(default_factory=list)

    # Doctrine, practices, texts
    key_belief_lemmas: List[str] = field(default_factory=list)
    key_practice_lemmas: List[str] = field(default_factory=list)
    primary_text_entities: List[Entity] = field(default_factory=list)
    institutional_entities: List[Entity] = field(default_factory=list)

    # Demographics and spread
    geographic_scope: List[Location] = field(default_factory=list)
    estimated_adherents: Optional[int] = None
    adherent_estimate_year: Optional[int] = None

    # Relationships and variants
    parent_traditions: List[Entity] = field(default_factory=list)
    derived_traditions: List[Entity] = field(default_factory=list)
    branches: List[Entity] = field(default_factory=list)

    # Generic extension points
    attributes: Dict[str, Any] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)


__all__ = ["ReligionIdeologyFrame"]
