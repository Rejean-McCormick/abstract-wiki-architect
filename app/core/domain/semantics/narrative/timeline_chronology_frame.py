# semantics\narrative\timeline_chronology_frame.py
"""
semantics/narrative/timeline_chronology_frame.py
------------------------------------------------

Aggregate frame for timelines / chronologies.

This module defines a language-independent representation for ordered
sequences of events associated with some subject (a person, organization,
conflict, project, etc.). It is intended for uses such as:

    - "Early life", "Career", "Later years" style biographical timelines.
    - Chronologies of wars, political crises, or scientific projects.
    - Project / program milestones.

The frame is deliberately neutral:

    - It stores `Event` objects and simple grouping hints.
    - It does not prescribe how many sentences to produce.
    - It does not deal with discourse-level decisions (e.g. which entries
      to omit); those are handled by planners / engines.

Typical usage
=============

    from semantics.types import Entity, Event, TimeSpan
    from semantics.narrative.timeline_chronology_frame import (
        TimelineChronologyFrame,
        TimelineEntry,
    )

    subject = Entity(id="Q7186", name="Marie Curie", human=True)

    birth = Event(
        id="E1",
        event_type="birth",
        participants={"subject": subject},
        time=TimeSpan(start_year=1867),
    )

    nobel_prize = Event(
        id="E2",
        event_type="award",
        participants={"laureate": subject},
        time=TimeSpan(start_year=1903),
        properties={"award_name": "Nobel Prize in Physics"},
    )

    timeline = TimelineChronologyFrame(
        subject=subject,
        entries=[
            TimelineEntry(event=birth, phase="early_life"),
            TimelineEntry(event=nobel_prize, phase="career", salience=1.5),
        ],
    )

Downstream NLG components can then decide how to group and verbalize
this information according to target language and desired length.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from semantics.types import Entity, Event, TimeSpan


@dataclass
class TimelineEntry:
    """
    Single entry in a timeline / chronology.

    The core of an entry is an `Event` (as defined in `semantics.types`),
    optionally enriched with:

        - a label or short description,
        - an explicit time span override,
        - a phase label for coarse grouping,
        - a salience weight.

    Fields
    ------

    event:
        The underlying `Event` this entry refers to. In many cases, the
        `Event.time` field will provide the primary temporal ordering
        signal for the timeline.

    label:
        Optional short label or description for the entry, suitable for
        headings or bullets (e.g. "Birth", "First Nobel Prize",
        "World War II"). Engines may choose to use this instead of, or
        in addition to, details from `event`.

    time_span:
        Optional explicit time span for this entry. If provided, this
        should be preferred for ordering and display; if omitted,
        `event.time` (if any) is used.

    phase:
        Optional coarse grouping label that can be used to cluster
        entries, for example:

            "early_life"
            "career"
            "later_years"
            "phase_1"
            "phase_2"

        The exact inventory is project-specific; the field is purely
        advisory.

    salience:
        Relative importance weight for the entry. A value of 1.0
        represents "normal" importance; higher values mark events that
        should be preferred when output must be shortened.

        The scale is not enforced; it is simply a hint for planners.

    extra:
        Opaque metadata or implementation-specific details for this
        entry. This is not interpreted by language-neutral NLG logic.
    """

    event: Event
    label: Optional[str] = None
    time_span: Optional[TimeSpan] = None
    phase: Optional[str] = None
    salience: float = 1.0
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TimelineChronologyFrame:
    """
    Aggregate frame representing a chronological sequence of events.

    This frame captures timelines *about* some subject (person, group,
    project, conflict, etc.), where each entry is a structured `Event`.
    It is the primary "49. Timeline / chronology frame" in the frame
    family inventory.

    Fields
    ------

    frame_type:
        Canonical frame-type string for routing and inspection. For this
        frame it is always "aggregate.timeline".

    subject:
        Optional `Entity` the timeline is primarily about. Typical
        values are persons, organizations, conflicts, or projects. Some
        timelines may represent broader topics without a single clear
        subject; in those cases this can be left as None.

    overall_span:
        Optional `TimeSpan` summarizing the temporal coverage of the
        timeline as a whole (earliest to latest relevant dates). When
        absent, downstream code may infer this from the entries.

    focus_interval:
        Optional `TimeSpan` marking the interval that should be
        emphasized in summaries (e.g. "World War II period", "first
        decade of career").

    entries:
        Ordered list of `TimelineEntry` objects representing the
        constituent events. The list is *intended* (but not required) to
        be sorted in chronological order according to `time_span` /
        `event.time`. Planners may reorder / filter as needed.

    ordering:
        Sorting strategy for the entries (e.g., "chronological", "reverse").
        Defaults to "chronological".

    grouping_hint:
        Optional high-level hint about how entries should be grouped for
        presentation. Examples (project-specific, not enforced):

            "by_phase"      – group by `TimelineEntry.phase`
            "by_decade"     – group by decade buckets of the time spans
            "by_century"    – group by centuries
            "by_topic"      – group using external topic labels

        Engines are free to ignore this field.

    attributes:
        Generic attribute map for timeline-level structured data, such as:

            {
                "max_entries": 10,
                "include_minor_events": False,
                "phase_order": ["early_life", "career", "later_years"]
            }

        Keys are free-form strings; values are expected to be
        JSON-serializable (str, int, float, list, dict, etc.).

    extra:
        Opaque metadata bag for pipeline-specific information, such as
        original AW payloads, provenance, or debugging flags. This is
        not interpreted by language-neutral NLG logic.
    """

    # Using field(default=..., init=False) ensures frame_type is:
    # 1. Included in asdict() (unlike ClassVar)
    # 2. Excluded from __init__ args (avoiding ordering errors)
    frame_type: str = field(default="aggregate.timeline", init=False)

    subject: Optional[Entity] = None
    overall_span: Optional[TimeSpan] = None
    focus_interval: Optional[TimeSpan] = None
    entries: List[TimelineEntry] = field(default_factory=list)

    ordering: str = "chronological"

    grouping_hint: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Defensive copying for container fields to avoid aliasing.
        self.entries = list(self.entries)
        self.attributes = dict(self.attributes)
        self.extra = dict(self.extra)


__all__ = ["TimelineEntry", "TimelineChronologyFrame"]
