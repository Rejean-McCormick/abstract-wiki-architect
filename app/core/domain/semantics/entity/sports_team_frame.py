# semantics\entity\sports_team_frame.py
"""
semantics/entity/sports_team_frame.py
-------------------------------------

Semantic frame for *sports teams* and *clubs*.

This frame covers professional and amateur clubs, national teams, and
other organized sports teams across different sports and competitions.

The frame is intentionally language-neutral: all surface realization is
handled later by the NLG layer (lexicon, morphology, constructions).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from semantics.types import Entity, Event, Location, TimeSpan


@dataclass
class SportsTeamFrame:
    """
    High-level frame for sports teams / clubs.

    Typical examples:
        - A professional football club in a national league
        - A national basketball team
        - A historic baseball franchise

    Fields
    ------

    frame_type:
        Constant identifying this family of frames. Used by routers
        and engines to dispatch to the right realization logic.

    main_entity:
        The team entity itself (e.g. “FC Barcelona”, “New York Yankees”).

    sport_lemmas:
        Lemmas describing the sport(s) the team plays, e.g.
        ["football"], ["basketball"], ["cricket"].

    team_type_lemmas:
        Lemmas describing the type of team, e.g.
        ["club"], ["national team"], ["women's team"].

    home_location:
        Geographic home location of the team, typically a city or
        region; may be `None` for teams whose identity is primarily
        national.

    home_venue:
        Primary stadium, arena, or ground where the team plays its
        home games.

    country:
        Optional country entity associated with the team (for national
        teams or clubs strongly associated with a country).

    leagues:
        List of entities representing the league(s) or competitions the
        team participates in (past or present), e.g. “Premier League”,
        “NBA”, “La Liga”.

    founding_event:
        Event describing the founding / establishment of the team.

    dissolution_event:
        Event describing the dissolution, relocation, or merger that
        ended the team’s existence, if applicable.

    active_timespan:
        Coarse-grained timespan summarizing the period during which the
        team has been active (start/end years).

    colors:
        List of primary team colors, e.g. ["red", "white"].

    nicknames:
        Common nicknames for the team, e.g. ["The Reds"].

    current_manager:
        Current head coach / manager, where such a role exists.

    current_captain:
        Current team captain, where such a role exists.

    notable_players:
        List of notable players historically associated with the team.

    honours_events:
        List of events representing important titles / honours, e.g.
        championship wins, cups, major trophies.

    attributes:
        Arbitrary attribute map of additional, team-specific
        information (e.g. "founded_as", "ownership_model",
        "supporter_groups", "rivalries").

    extra:
        Opaque metadata bag for passing through original source
        structures (e.g. raw JSON, Wikidata statements, etc.).
    """

    frame_type: str = "sports-team"
    main_entity: Entity = field(default_factory=Entity)

    sport_lemmas: List[str] = field(default_factory=list)
    team_type_lemmas: List[str] = field(default_factory=list)

    home_location: Optional[Location] = None
    home_venue: Optional[Location] = None
    country: Optional[Entity] = None

    leagues: List[Entity] = field(default_factory=list)

    founding_event: Optional[Event] = None
    dissolution_event: Optional[Event] = None
    active_timespan: Optional[TimeSpan] = None

    colors: List[str] = field(default_factory=list)
    nicknames: List[str] = field(default_factory=list)

    current_manager: Optional[Entity] = None
    current_captain: Optional[Entity] = None
    notable_players: List[Entity] = field(default_factory=list)

    honours_events: List[Event] = field(default_factory=list)

    attributes: Dict[str, Any] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)


__all__ = ["SportsTeamFrame"]
