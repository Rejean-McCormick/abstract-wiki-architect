# semantics\entity\organization_frame.py
"""
semantics/entity/organization_frame.py
--------------------------------------

High-level semantic frame for organization / group entities.

This module defines a small, typed data class that captures the core
semantic information needed to generate Wikipedia-style introductory
sentences and short summaries for organizations, companies, parties,
clubs, etc.

The frame is deliberately conservative: it encodes only stable,
language-neutral information (entities, locations, event-like facts,
and lemma-level labels). Any language-specific realization (wording,
inflection, constructions) is handled elsewhere in the pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from semantics.types import Entity, Event, Location


@dataclass
class OrganizationFrame:
    """
    Organization-level semantic frame.

    Typical use cases include articles about:

        - Companies and corporations
        - Political parties and movements
        - Non-profit organizations and NGOs
        - Sports clubs and teams (where you want an organization-first view)
        - Academic institutions, foundations, associations, etc.

    The goal is to provide enough structure for:

        - First-sentence definitional descriptions
          (“X is a Y Z headquartered in A.”)
        - Simple historical facts (founding, dissolution)
        - Basic structural relations (parent group, subsidiaries, key people)

    Fields
    ------

    main_entity:
        The organization the description is about.

        This should be an `Entity` whose `name` is the canonical label
        (e.g. "OpenAI", "FC Barcelona"). The `Entity` may also carry an
        `id` (e.g. Wikidata QID) and arbitrary metadata in `extra`.

    organization_type_lemmas:
        List of language-neutral lemmas describing the *kind* of
        organization, e.g.:

            ["company"]
            ["political party"]
            ["non-governmental organization"]

        These are not surface strings; they are lemmas that the lexicon /
        morphology layer will map to language-specific words.

    sector_lemmas:
        List of lemmas describing the economic or activity sector, e.g.:

            ["technology"]
            ["banking"]
            ["higher education"]

        Can be empty if the sector is not known or not relevant.

    country_lemmas:
        List of lemmas encoding national or regional affiliation that are
        useful for adjectival realizations, e.g.:

            ["american"]
            ["french"]
            ["european"]

        This is analogous to `nationality_lemmas` in `BioFrame`, but for
        organizations (“American technology company”, “French bank”, etc.).

    headquarters:
        Optional primary headquarters location for the organization.

        Represented as a `Location` (typically with `name` and optional
        country code). If an organization has multiple important offices,
        you can either choose the canonical one here or encode the rest
        under `attributes`.

    founding_event:
        Optional `Event` describing the founding/establishment of the
        organization.

        Conventionally, `event_type` might be set to "founding" or a
        similar project-specific label, and:

            - `time` holds the founding date / year
            - `location` holds the place of founding
            - `participants` may include founders, initial sponsors, etc.

    dissolution_event:
        Optional `Event` describing the dissolution / closure / merger
        that ended the organization’s independent existence, if applicable.

        Conventionally, `event_type` might be "dissolution", "closure",
        "merger", etc.

    other_events:
        List of other salient events in the organization’s history, such as:

            - mergers and acquisitions
            - rebrandings
            - relocations
            - major achievements or scandals

        Each is represented as a generic `Event`. The rendering pipeline
        decides which events to surface and how.

    key_people:
        Mapping from role label → list of people (`Entity` instances).

        Examples of role labels (free-form strings):

            "founder"
            "cofounder"
            "chairperson"
            "chief_executive_officer"
            "president"
            "manager"
            "coach"

        The labels are deliberately unconstrained; any normalization or
        mapping to canonical role inventories is done later.

        Example:

            {
                "founder": [Entity(...), Entity(...)],
                "chief_executive_officer": [Entity(...)]
            }

    parent_organizations:
        List of entities representing parent organizations, if any.

        For example, a subsidiary company may have its parent corporation
        here. If multiple parents exist (joint ventures, complex holdings),
        they can all be listed.

    subsidiaries:
        List of entities representing notable subsidiaries or controlled
        organizations.

        This is typically used only for prominent downstream entities that
        might be mentioned in the intro or follow-up sentences.

    predecessors:
        List of organizations that this organization directly succeeded
        (e.g. after a merger, reorganization, or renaming).

    successors:
        List of organizations that directly succeed this one (e.g. after
        a merger, breakup, or major restructuring).

    attributes:
        Arbitrary attribute map for the organization, using JSON-friendly
        values (strings, numbers, lists, dicts). Typical keys might include:

            {
                "founded_year": 2015,
                "employees": 10000,
                "revenue": {"amount": 1000000000, "currency": "USD", "year": 2023},
                "stock_ticker": "XYZ",
                "league": "La Liga"
            }

        The exact schema is project-specific; the NLG layer may look for a
        small set of known keys but should tolerate arbitrary ones.

    extra:
        Arbitrary metadata that does not directly participate in
        realization but is useful for debugging, tracing, or bridging
        back to the original data source, for example:

            {
                "wikidata_qid": "Q12345",
                "source_row": 17,
                "raw": {...}
            }
    """

    main_entity: Entity
    organization_type_lemmas: List[str] = field(default_factory=list)
    sector_lemmas: List[str] = field(default_factory=list)
    country_lemmas: List[str] = field(default_factory=list)
    headquarters: Optional[Location] = None
    founding_event: Optional[Event] = None
    dissolution_event: Optional[Event] = None
    other_events: List[Event] = field(default_factory=list)
    key_people: Dict[str, List[Entity]] = field(default_factory=dict)
    parent_organizations: List[Entity] = field(default_factory=list)
    subsidiaries: List[Entity] = field(default_factory=list)
    predecessors: List[Entity] = field(default_factory=list)
    successors: List[Entity] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)


__all__ = ["OrganizationFrame"]
