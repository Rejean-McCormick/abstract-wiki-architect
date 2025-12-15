# semantics\narrative\career_season_campaign_summary_frame.py
# semantics/narrative/career_season_campaign_summary_frame.py

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from semantics.types import Event, TimeSpan
from semantics.all_frames import register_frame_type


@dataclass
class CareerPhase:
    """
    One coherent phase within a career / season / campaign trajectory.

    Examples:
        - "Early career", "Prime", "Later career"
        - "Regular season", "Playoffs"
        - "Primary campaign", "General election campaign"

    Fields
    ------

    label:
        Human-readable label for the phase in a neutral, language-agnostic
        form. Typically a short English-like string that can be mapped or
        rephrased downstream.

    span:
        Optional `TimeSpan` covering this phase (season, set of years,
        specific dates, etc.). If omitted, planners may infer timing from
        `key_events`.

    key_events:
        List of `Event` objects representing salient happenings within
        this phase, e.g.:
            - publication of major works,
            - key matches or finals,
            - election dates, debates, or major speeches.

        Event-level renderers can turn these into individual sentences if
        a more detailed narrative is desired.

    metrics:
        Domain-specific numeric or categorical metrics for this phase,
        such as:
            - {"goals": 30, "appearances": 40}
            - {"votes_percentage": 52.4}
            - {"books_published": 5}

        The keys are free-form strings; values should be JSON-friendly
        (numbers, strings, lists, dicts).
    """

    label: str
    span: Optional[TimeSpan] = None
    key_events: List[Event] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)


@register_frame_type("aggregate.career_summary")
@dataclass
class CareerSeasonCampaignSummaryFrame:
    """
    Narrative / aggregate frame for careers, sports seasons, and campaigns.

    This frame provides a compact, planner-friendly summary of a single
    coherent trajectory, such as:

        - a person's career,
        - a sports club's season,
        - a political campaign or term in office.

    It is a specialized variant of a timeline frame with additional
    support for domain-specific metrics (goals, titles, votes, works
    produced, etc.) and optional grouping into phases.

    Fields
    ------

    frame_type:
        Stable type label used for routing and family lookup.
        Canonical value: "aggregate.career_summary".

    subject_id:
        Identifier of the primary subject whose trajectory is being
        summarized. This typically refers to:
            - a person frame (for a player, author, politician),
            - a team / club frame (for a season),
            - an organization or party (for a campaign).

        The actual entity data lives elsewhere (e.g. in a `PersonFrame`
        or `SportsTeamFrame`), accessible via this ID.

    domain:
        Coarse domain label for the trajectory, such as:
            - "literature", "music"
            - "football", "basketball"
            - "politics", "diplomacy"

        This helps downstream logic choose domain-specific constructions
        and interpret metrics.

    span:
        Optional overall `TimeSpan` for the whole career / season /
        campaign being summarized. For a season, this might be a single
        year span; for a career, it might be several decades.

    phases:
        Ordered list of `CareerPhase` objects. These represent major
        internal segments of the trajectory, for example:
            - "Early career", "Prime", "Later career"
            - "Regular season", "Playoffs"
            - "Primary campaign", "General election"

        Planners may choose to:
            - emit one sentence per phase,
            - or collapse phases into a shorter summary using `metrics`.

    metrics:
        Aggregate metrics for the entire trajectory, in a JSON-friendly
        dictionary. Examples:

            {
                "books_published": 50,
                "goals": 200,
                "appearances": 400,
                "wins": 25,
                "losses": 5,
                "votes_percentage": 52.4,
            }

        Keys are domain-specific; NLG components can look for known keys
        but should tolerate arbitrary ones.

    headline:
        Optional short, neutral headline-style summary of the trajectory,
        intended as a semantic hint rather than a ready-made sentence.

        Examples:
            - "Prolific thriller writer with four decades of work"
            - "League runners-up and national cup finalists"
            - "Won the presidency with a narrow majority"

        This may be used to bias or override automatically composed
        summaries when present.

    extra:
        Opaque metadata bag for pipeline-specific or provenance data,
        such as:
            - original JSON snippets,
            - source IDs,
            - debugging notes.

        This is not interpreted by language-independent NLG logic.
    """

    frame_type: str = "aggregate.career_summary"

    subject_id: Optional[str] = None
    domain: Optional[str] = None
    span: Optional[TimeSpan] = None
    phases: List[CareerPhase] = field(default_factory=list)

    # Summary metrics for the whole trajectory
    metrics: Dict[str, Any] = field(default_factory=dict)
    headline: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


__all__ = ["CareerSeasonCampaignSummaryFrame", "CareerPhase"]
