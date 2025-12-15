# semantics\relational\role_position_office_frame.py
"""
semantics/relational/role_position_office_frame.py
--------------------------------------------------

High-level relational frame for roles, positions, and offices.

This module defines a semantic frame for facts of the form:

    - "X served as Y of Z from A to B."
    - "X was appointed Y in Z in YEAR."
    - "X is the nth Y of Z."

Typical examples:

    - "Angela Merkel served as Chancellor of Germany from 2005 to 2021."
    - "Pep Guardiola is the manager of Manchester City."
    - "Barack Obama was the 44th president of the United States."

The frame is deliberately language-neutral and focuses on:

    - who holds or held the role (office holder),
    - what the role/office is (lemmas like "president", "manager"),
    - which organization or jurisdiction it is attached to,
    - when the term started and ended,
    - who the predecessor and successor are,
    - whether the role is acting / interim,
    - a small bag of extra structured attributes.

Any surface realization (word choice, morphology, syntax) is handled in
later stages of the pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from semantics.types import Entity, Event, Location, TimeSpan


@dataclass
class RolePositionOfficeFrame:
    """
    Relational frame for holding an office, role, or position.

    This frame is intended to capture statements like:

        - "X served as Y of Z from A to B."
        - "X is the Y of Z."
        - "X became Y in YEAR, succeeding W."

    where:

        - X  = office holder (a person or, rarely, an organization)
        - Y  = role / office (e.g. "president", "manager", "CEO")
        - Z  = organization or jurisdiction (e.g. "France", "AC Milan")
        - A–B = time span / term in office

    Fields
    ------

    office_holder:
        The entity that holds or held the office / role (typically an
        `Entity` with `human=True`).

        Example:
            Entity(id="Q567", name="Angela Merkel", human=True)

    role_lemmas:
        List of lemma-like labels for the role / office itself, such as:

            ["chancellor"]
            ["president"]
            ["prime minister"]
            ["manager"]
            ["chief_executive_officer"]

        These are language-neutral keys that the lexicon / NLG layer
        will map to language-specific words.

    organization:
        Optional `Entity` representing the organization for which the
        role is held, such as:

            - a sports club ("FC Barcelona")
            - a company ("OpenAI")
            - a political party ("Conservative Party")

        This is particularly common for roles like "CEO of X",
        "manager of X", "coach of X".

    jurisdiction:
        Optional `Entity` representing the political or geographic
        jurisdiction associated with the office, such as:

            - a country ("Germany")
            - a region ("Bavaria")
            - a city ("Paris")

        For many offices, either `organization` or `jurisdiction` will
        be populated, but not necessarily both. Engines can prefer one
        or synthesize text from both if needed.

    seat_location:
        Optional `Location` describing where the office is formally
        seated (e.g. "Berlin", "Vatican City"), if this is relevant to
        downstream text.

    term:
        Optional `TimeSpan` giving the overall duration of the term in
        office, typically with `start_year` and `end_year` (and optional
        month/day granularity if available).

        Example:
            TimeSpan(start_year=2005, end_year=2021)

    start_event:
        Optional `Event` describing how or when the term began, such as
        an election, appointment, or inauguration. Conventionally,
        `event_type` might be:

            "election", "appointment", "inauguration"

        and the event would contain:

            - time  (TimeSpan)
            - location (Location)
            - participants (e.g. "winner": office_holder)

    end_event:
        Optional `Event` describing how or when the term ended, such as
        a resignation, defeat in an election, dismissal, or death in
        office.

        Conventionally, `event_type` might be:

            "resignation", "dismissal", "defeat", "death"

    ordinal:
        Optional integer indicating the ordinal number of the office
        holder, for patterns like:

            - "44th president of the United States"
            - "third manager of the club"

        The NLG layer is responsible for converting integers to ordinal
        strings per language.

    acting:
        Optional boolean flag indicating that the role is/was held in an
        acting or interim capacity (e.g. "acting president"). If `None`,
        no information is implied.

    incumbent:
        Optional boolean indicating whether the holder is (at the
        reference time) still in office.

        - True  → currently in office
        - False → no longer in office
        - None  → unspecified / unknown

        This is useful for distinguishing between "served as" and "is".

    predecessor:
        Optional `Entity` representing the immediate predecessor in this
        office, if known.

    successor:
        Optional `Entity` representing the immediate successor in this
        office, if known.

    attributes:
        Generic attribute map for structured but project-specific data,
        for example:

            {
                "term_label": "First term",
                "coalition": ["CDU", "CSU", "SPD"],
                "major_portfolio": ["foreign_policy", "economy"]
            }

        Keys are free-form strings; values should be JSON-serializable
        (str, int, float, list, dict, etc.).

    extra:
        Arbitrary metadata that is not interpreted by language-neutral
        NLG logic but may be useful for tracing, debugging, or bridging
        back to the original source format. For example:

            {
                "wikidata_statement_id": "Q567-P39-1234ABCD",
                "raw": {...}
            }
    """

    office_holder: Entity
    role_lemmas: List[str] = field(default_factory=list)
    organization: Optional[Entity] = None
    jurisdiction: Optional[Entity] = None
    seat_location: Optional[Location] = None
    term: Optional[TimeSpan] = None
    start_event: Optional[Event] = None
    end_event: Optional[Event] = None
    ordinal: Optional[int] = None
    acting: Optional[bool] = None
    incumbent: Optional[bool] = None
    predecessor: Optional[Entity] = None
    successor: Optional[Entity] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)


__all__ = ["RolePositionOfficeFrame"]
