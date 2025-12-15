# semantics\entity\project_program_frame.py
"""
semantics/entity/project_program_frame.py
========================================

High-level semantic frame for projects, programmes, and initiatives.

This frame family is intended for things like:

- government programmes,
- international development projects,
- scientific research projects,
- public campaigns and initiatives,
- large-scale missions (e.g. space missions as programmes).

It is *entity-centric*: the main subject is the project / programme
itself, not a single event inside it. Temporal information is captured
by a coarse time span plus optional key events.

The concrete lexical and syntactic realization is handled elsewhere
(engines + constructions). This module only defines the abstract data
shape that those components expect.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from semantics.types import Entity, Event, Location, TimeSpan
from semantics.common.entity_base import BaseEntityFrame


@dataclass
class ProjectProgramFrame(BaseEntityFrame):
    """
    Semantic frame for a project, programme, or initiative.

    This extends the generic ``BaseEntityFrame`` with fields that are
    typical for encyclopedic descriptions of projects and programmes.

    The underlying project / programme itself is represented by
    ``main_entity`` (inherited from ``BaseEntityFrame``). That entity
    will usually have:

        - a canonical name (e.g. "Green Homes Grant"),
        - an identifier (e.g. a Wikidata QID),
        - an ``entity_type`` hint such as "project", "programme",
          "initiative", or "mission".

    Fields
    ------
    frame_type:
        String label identifying this frame family, used by routing
        or debugging layers. For this class it is always
        ``"project_program"``.
    label:
        Optional short label or subtitle for the project, separate
        from ``main_entity.name``. For example, a slogan or
        descriptive tag line.
    kind:
        Coarse classification of the project, e.g.
        "government_programme", "research_project",
        "public_health_campaign", "space_mission".
    sponsors:
        Organisations or entities that formally sponsor or fund the
        project (ministries, agencies, foundations, etc.).
    implementing_organizations:
        Organisations responsible for day-to-day implementation
        (executing agencies, contractors, research institutions).
    partners:
        Other notable partner entities involved in delivery.
    time_span:
        Overall time span of the project or programme (planned or
        actual). For more detailed timelines, use ``key_events``.
    status:
        High-level status string, e.g. "planned", "ongoing",
        "completed", "suspended", "cancelled".
    objectives:
        List of short textual objectives or goals, in a neutral,
        language-independent form (simple English labels or keys).
    focus_areas:
        Optional thematic focus areas, such as "renewable_energy",
        "primary_education", "public_health", "infrastructure".
    target_locations:
        Locations where the project is implemented or primarily
        focused (countries, regions, cities).
    target_populations:
        Short textual descriptions of main beneficiary groups, e.g.
        "low_income_households", "smallholder_farmers",
        "urban_commuters".
    budget_amount:
        Approximate total budget figure as a raw number. The unit is
        interpreted via ``budget_currency``. This is intentionally
        numeric so that callers can derive comparative statements.
    budget_currency:
        ISO currency code or free string label for the budget
        (e.g. "USD", "EUR", "JPY").
    budget_year:
        Reference year for the budget figure, if applicable.
    key_events:
        Salient events in the life of the project (launch,
        extensions, major milestones, cancellations, etc.). Each
        event should use a consistent ``event_type`` inventory,
        e.g. "launch", "extension", "phase_completion".
    outcomes_summary:
        Optional short free-text summary of outcomes or impact, still
        at an abstract level (e.g. "increased vaccination coverage
        in target regions").
    metrics:
        Arbitrary key → value map for quantitative indicators and
        other machine-readable metrics (e.g. {"houses_retrofitted":
        250000, "beneficiaries_estimated": 1_200_000}).

    Notes
    -----
    - Generic per-entity attributes and metadata (if provided by the
      calling code) should be passed via the ``attributes`` and
      ``extra`` fields defined on ``BaseEntityFrame``.
    - All string fields are intended to be language-neutral keys or
      simple English labels. Lexicalization into the target language
      is handled by higher layers.
    """

    frame_type: str = "project_program"

    # Descriptive classification
    label: Optional[str] = None
    kind: Optional[str] = None

    # Actors and governance
    sponsors: List[Entity] = field(default_factory=list)
    implementing_organizations: List[Entity] = field(default_factory=list)
    partners: List[Entity] = field(default_factory=list)

    # Scope and targets
    time_span: Optional[TimeSpan] = None
    status: Optional[str] = None
    objectives: List[str] = field(default_factory=list)
    focus_areas: List[str] = field(default_factory=list)
    target_locations: List[Location] = field(default_factory=list)
    target_populations: List[str] = field(default_factory=list)

    # Budget / resources
    budget_amount: Optional[float] = None
    budget_currency: Optional[str] = None
    budget_year: Optional[int] = None

    # Timeline and impact
    key_events: List[Event] = field(default_factory=list)
    outcomes_summary: Optional[str] = None

    # Machine-readable indicators
    metrics: Dict[str, Any] = field(default_factory=dict)


__all__ = ["ProjectProgramFrame"]
