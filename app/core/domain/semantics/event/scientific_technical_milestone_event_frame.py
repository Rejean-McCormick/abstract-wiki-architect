# semantics\event\scientific_technical_milestone_event_frame.py
"""
semantics/event/scientific_technical_milestone_event_frame.py
=============================================================

High-level semantic frame for **scientific / technical milestone events**.

This family is intended for events such as:

- scientific discoveries,
- technical inventions,
- landmark experiments or demonstrations,
- first launches / deployments of technologies,
- key publications that mark a turning point.

It is *event-centric*: the main subject of the frame is a milestone event
(or a very small cluster of closely related events), rather than a person
or organization. Typical usages include:

- Lead sentences of articles about discoveries or inventions,
- Biographical sentences highlighting a person's key discovery,
- Summaries of important missions or experiments in a field.

The concrete lexical and syntactic realization is handled elsewhere
(engines + constructions). This module only defines the abstract data
shape that those components expect.

Design principles
=================

- Keep **semantics only** here (no language-specific morphology).
- Reuse the generic :class:`Event` / :class:`Entity` / :class:`TimeSpan`
  / :class:`Location` types from ``semantics.types``.
- Treat this as a **thin wrapper** around one main ``Event`` plus
  optional related events and metadata.
- Prefer small, typed fields (lists of lemmas, entities, locations)
  over free text; use ``attributes`` / ``extra`` for everything else.

Example usage
=============

    from semantics.types import Entity, Event, Location, TimeSpan
    from semantics.event.scientific_technical_milestone_event_frame import (
        ScientificTechnicalMilestoneEventFrame,
    )

    einstein = Entity(id="Q937", name="Albert Einstein", entity_type="person", human=True)
    annus_mirabilis_paper = Event(
        id="E1905",
        event_type="publication",
        label="On the Electrodynamics of Moving Bodies",
        participants=[einstein],
        time=TimeSpan(start_year=1905),
        location=Location(id="L1", name="Annalen der Physik", kind="journal"),
    )

    frame = ScientificTechnicalMilestoneEventFrame(
        main_event=annus_mirabilis_paper,
        subject=einstein,
        domain_lemmas=["physics"],
        topic_keywords=["special relativity"],
    )

Downstream components can then generate sentences such as:

- "In 1905, Albert Einstein published a landmark paper on special relativity."
- "The theory of special relativity was introduced in a 1905 paper by Albert Einstein."
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from semantics.types import Entity, Event, Location, TimeSpan


@dataclass
class ScientificTechnicalMilestoneEventFrame:
    """
    Semantic frame for scientific / technical milestone events.

    The goal is to support short, information-dense summaries of milestones
    such as discoveries, inventions, experiments, publications, launches, and
    other "firsts" in science and technology.

    Core identity
    -------------

    main_event:
        The primary :class:`Event` representing the milestone itself. Typical
        ``event_type`` values (see ``docs/FRAMES_EVENT.md``) include:

            - "discovery"
            - "invention"
            - "experiment"
            - "demonstration"
            - "publication"
            - "launch"
            - "first_use"

        Engines and planners are expected to read time, location, and
        participants from this event when building sentences.

    frame_type:
        Stable label for routing / planning. For this frame family we use
        ``"event.scientific_milestone"``. This string is also returned by
        :func:`semantics.all_frames.get_frame_family_name` for the
        ``"scientific_milestone"`` / ``"technical_milestone"`` family.

    subject:
        Optional :class:`Entity` that the milestone is "about" from a
        discourse perspective. Examples:

            - the scientist whose biography this belongs to,
            - the organization or mission responsible for the milestone,
            - the theory / product being introduced.

        This lets discourse planners speak either from the perspective of
        the person ("X discovered Y") or the phenomenon/technology ("Y was
        discovered by X").

    Domain and topic
    ----------------

    domain_lemmas:
        High-level domain labels, e.g.::

            ["physics"]
            ["chemistry"]
            ["computer_science"]
            ["aerospace_engineering"]

        These are language-neutral lemma keys that a lexicon or engine can
        map to concrete surface forms per language ("in physics",
        "in computer science", etc.).

    topic_keywords:
        Finer-grained topic or phenomenon labels, e.g.::

            ["radioactivity"]
            ["special_relitivity"]  # sic: key form, not surface
            ["dna_structure"]

        Engines may use these for phrases like "in the field of X" or
        "known for work on X and Y".

    Time and location
    -----------------

    time:
        Optional :class:`TimeSpan` overriding or supplementing
        ``main_event.time`` for the purposes of high-level summaries.
        If ``None``, consumers should read directly from
        ``main_event.time`` when present.

    location:
        Optional :class:`Location` overriding or supplementing
        ``main_event.location``. Useful when the milestone is best talked
        about at a different granularity than the underlying event
        (e.g. "in Paris" vs. a specific laboratory).

    Related events and metrics
    --------------------------

    related_events:
        Other salient :class:`Event` objects closely tied to the milestone,
        such as:

            - follow-up experiments,
            - initial deployment / commercialization events,
            - related award or prize events.

        These are optional and primarily useful for multi-sentence summaries
        or richer timelines.

    metrics:
        Arbitrary key → value map for structured indicators, for example::

            {"citation_count": 12000, "impact_factor": 42.1}

        This is deliberately free-form so that callers can attach
        machine-readable statistics without changing the dataclass.

    Generic extension hooks
    -----------------------

    attributes:
        Generic attribute bag for additional structured information that
        does not justify its own top-level field, such as::

            {
                "methodology": ["double_blind", "randomized_controlled_trial"],
                "instrument": ["hadron_collider"],
            }

    extra:
        Free-form extension map for anything else. Intended for data that
        is not (yet) standardized but that callers still want to preserve.

    Notes
    -----

    - This frame does not prescribe any particular event inventory beyond
      the general guidance in ``docs/FRAMES_EVENT.md``. Callers should use
      a consistent set of ``event_type`` values for ``main_event`` and
      the entries in ``related_events``.
    - Lexicalization into the target language is handled by higher layers.
    """

    # Stable identifier for this frame family, for routing / introspection.
    frame_type: str = "event.scientific_milestone"

    # Core milestone event and subject
    main_event: Optional[Event] = None
    subject: Optional[Entity] = None

    # Domain and topic labels
    domain_lemmas: List[str] = field(default_factory=list)
    topic_keywords: List[str] = field(default_factory=list)

    # Optional overrides / coarse-grained time and place
    time: Optional[TimeSpan] = None
    location: Optional[Location] = None

    # Additional events tightly linked to the milestone
    related_events: List[Event] = field(default_factory=list)

    # Machine-readable metrics / indicators
    metrics: Dict[str, Any] = field(default_factory=dict)

    # Generic extension hooks
    attributes: Dict[str, Any] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)


__all__ = ["ScientificTechnicalMilestoneEventFrame"]
