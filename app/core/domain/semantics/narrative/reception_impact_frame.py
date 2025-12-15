# semantics\narrative\reception_impact_frame.py
"""
semantics/narrative/reception_impact_frame.py
---------------------------------------------

Narrative / aggregate frame for **reception** and **impact / legacy**.

This frame is intended for sections such as “Reception”, “Legacy”, or
“Impact” in encyclopedic articles. It captures:

- Critical and public reception (who said what, about which aspect, when).
- Domains of impact (which fields or areas were influenced, and how).
- Optional quantitative metrics (box office, citations, ratings, etc.).
- Award events, remakes, key adoptions, and other notable follow-ups.

The frame is designed to be language-agnostic and planner-friendly:
engines and discourse planners can cluster `ReceptionItem`s and
`ImpactDomain`s into 1–3 sentences like:

    - “The film received positive reviews from critics, who praised X but
      criticized Y.”
    - “The theory has had a lasting impact on Z, influencing A and B.”

All surface-form choices are delegated to downstream NLG components
(lexicon, morphology, constructions).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from semantics.types import Entity, Event, TimeSpan


@dataclass
class ReceptionItem:
    """
    One *source × stance × topic* item within reception.

    Examples
    --------
    - A single critic's review (source = that critic or publication).
    - Aggregated public sentiment for a topic (“audiences praised the visuals”).
    - A community or institution’s position on some aspect of the work.

    Fields
    ------
    source:
        Entity representing the source of the reception signal:
        critic, publication, outlet, community, award body, etc.
        May be None if the source is implicit or generic (“critics”, “audiences”).
        (Note: Previously named `source_entity`).

    aspect:
        The specific aspect being commented on (e.g. "visuals", "script",
        "critical_reception").

    summary:
        Brief summary of the reception content.

    representative_quote:
        A direct quote summarizing the reception (optional).

    stance:
        Coarse label for attitude, e.g.:

            "positive", "mixed", "negative"

        Additional project-specific labels are allowed and preserved.

    topic:
        Optional textual label for the aspect being commented on, e.g.:

            "performance", "script", "visuals", "methodology"

    time_span:
        Optional `TimeSpan` indicating when the reception occurred
        (release period, review date range, etc.).

    attributes:
        Additional structured properties, such as:

            {
                "quote_id": "Q1",
                "rating": 4.5,
                "scale": "stars_5",
                "review_url": "https://example.org/...",
            }
    """

    # Fields required by tests
    source: Optional[Entity] = None
    aspect: str = "general"
    summary: str = ""
    representative_quote: Optional[str] = None

    # Original semantic fields
    stance: Optional[str] = None
    topic: Optional[str] = None
    time_span: Optional[TimeSpan] = None

    # Extensibility
    attributes: Dict[str, Any] = field(default_factory=dict)

    # Backward compatibility for 'properties'
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ImpactDomain:
    """
    One domain / field in which the subject has had an impact.

    Typical domains
    ---------------
    - "physics", "mathematics", "cinema", "literature"
    - "civil rights", "environmental policy"
    - "popular culture", "video games"

    Fields
    ------
    domain_label:
        Short label for the domain of impact.

    summary:
        A textual summary of the impact in this domain.

    examples:
        A list of string examples or citations illustrating the impact.

    metrics:
        Quantitative measures of impact in this domain (e.g. {"citations": 120}).

    description_properties:
        Bag of properties that can be used by planners / engines to
        describe the impact in more detail, e.g.:

            {
                "description_lemmas": ["influence", "inspiration"],
                "examples": ["Film A", "Movement B"],
                "summary": "Widely cited in later work on X.",
            }

    key_events:
        List of `Event` objects representing concrete manifestations of
        impact, such as:

        - major citations or adoptions,
        - landmark remakes or adaptations,
        - significant policy changes linked to the work/idea.
    """

    # Fields required by tests
    domain_label: str
    summary: Optional[str] = None
    examples: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)

    # Original semantic fields
    description_properties: Dict[str, Any] = field(default_factory=dict)
    key_events: List[Event] = field(default_factory=list)


@dataclass
class ReceptionImpactFrame:
    """
    Narrative frame capturing **reception** and **impact / legacy** for a subject.

    This is a high-level aggregate frame, typically used at the paragraph
    or section level, not for single sentences in isolation.

    Fields
    ------
    frame_type:
        Stable identifier for this frame family. Engines and planners
        can dispatch on this; value is `"aggregate.reception"`.

    subject_id:
        Optional identifier string for the subject (e.g. "Q42").

    subject:
        Optional `Entity` object the reception/impact is about.

    critical_reception:
        List of `ReceptionItem`s representing critical reception
        (critics, professional reviewers, academic commentary, etc.).

    public_reception:
        List of `ReceptionItem`s representing public or audience
        reception (general audiences, user ratings, fan communities).

    impact_domains:
        List of `ImpactDomain`s describing areas where the work/idea
        has had influence or lasting effect.

    metrics:
        Optional quantitative or categorical metrics (global), e.g.:

            {
                "box_office_usd": 100_000_000,
                "opening_weekend_usd": 50_000_000,
                "citations_count": 1200,
                "imdb_rating": 7.8,
                "rotten_tomatoes_tomato_meter": 95,
            }

        Exact keys are project-specific; engines may look for a small
        known subset and otherwise ignore unknown metrics.

    awards:
        List of award-related events, represented as `Event` objects
        (e.g. `Event(event_type="award", ...)`), such as:

            - nominations,
            - wins at festivals or ceremonies,
            - prizes and honors.

    extra:
        Free-form metadata bag for pipeline-specific information,
        original JSON, or debugging data that should pass through
        unchanged.
    """

    # Fix: Use field(init=False) so it appears in asdict() but doesn't break init order
    frame_type: str = field(default="aggregate.reception", init=False)

    # Identity
    subject_id: Optional[str] = None
    subject: Optional[Entity] = None

    # Reception
    critical_reception: List[ReceptionItem] = field(default_factory=list)
    public_reception: List[ReceptionItem] = field(default_factory=list)

    # Generic items list (if not split by critical/public)
    items: List[ReceptionItem] = field(default_factory=list)

    # Impact / legacy
    impact_domains: List[ImpactDomain] = field(default_factory=list)

    overall_sentiment: Optional[str] = None
    legacy_summary: Optional[str] = None

    # Optional quantitative or categorical metrics
    metrics: Dict[str, Any] = field(default_factory=dict)
    awards: List[Event] = field(default_factory=list)

    # Extension
    attributes: Dict[str, Any] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)


__all__ = [
    "ReceptionImpactFrame",
    "ReceptionItem",
    "ImpactDomain",
]
