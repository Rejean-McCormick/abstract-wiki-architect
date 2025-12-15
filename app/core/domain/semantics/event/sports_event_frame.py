# semantics\event\sports_event_frame.py
# semantics/event/sports_event_frame.py
#
# SportsEventFrame
# =================
#
# Thin, typed specialization of `Event` for sports-related events:
# matches, fixtures, seasons, and tournaments.
#
# This class does not introduce new fields beyond `Event`; instead, it
# provides a dedicated `frame_type` ("event.sports") so that sports
# events can be routed and serialized as a distinct frame family within
# the general `semantics.all_frames` machinery.
#
# Semantics
# ---------
# The underlying `Event` fields are interpreted with the following
# conventions for sports data:
#
#   - id:
#       Stable identifier for the sports event, if any (e.g. a match ID,
#       season ID, or internal key).
#
#   - event_type:
#       High-level sports event label, typically one of (but not limited to):
#
#           "match"        – a single game or fixture
#           "season"       – an entire league / competition season
#           "tournament"   – a cup or knock-out style competition
#           "round"        – a particular round or stage within a tournament
#           "playoff"      – a playoff series or tie
#
#       The inventory is project-specific; these are only recommended
#       values for interoperability.
#
#   - participants:
#       Mapping from role label → Entity. Common role keys:
#
#           "home_team"    – home team in a match
#           "away_team"    – away team in a match
#           "team1", "team2"
#           "winner"       – overall winner (team or player)
#           "runner_up"
#           "referee"
#           "venue_owner"
#
#       Additional, project-specific roles are allowed and should be
#       tolerated by downstream components.
#
#   - time:
#       TimeSpan indicating when the match / season / tournament took
#       place (kick-off date, season years, etc.).
#
#   - location:
#       Venue or primary location of the event (stadium, city, country).
#
#   - properties:
#       Arbitrary additional semantic properties. Typical keys for sports:
#
#           {
#               "competition": Entity(...),         # league or cup
#               "season_entity": Entity(...),       # optional season object
#               "stage": "group stage",
#               "round_label": "Quarter-finals",
#               "leg": 1,                           # for two-legged ties
#               "home_score": 2,
#               "away_score": 1,
#               "score": "2–1",
#               "aggregate_score": "3–2",
#               "extra_time": True,
#               "penalty_shootout_score": "5–4",
#               "attendance": 60000,
#           }
#
#       The exact schema is intentionally flexible so that different
#       sports and data sources can be supported without schema changes.
#
#   - extra:
#       Opaque metadata bag for tracing back to original sources (raw
#       JSON rows, Wikidata statements, log provenance, etc.).
#
# Usage
# -----
# Sports events can either be constructed directly as `SportsEventFrame`
# instances or produced via normalization code that maps raw data to this
# structure. The NLG router can then dispatch on `frame_type ==
# "event.sports"` to pick sports-specific realization logic.
#

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from semantics.types import Event
from semantics.all_frames import register_frame_type


@register_frame_type("event.sports")
@dataclass
class SportsEventFrame(Event):
    """
    SportsEventFrame

    Specialization of :class:`semantics.types.Event` for sports-related
    events (matches, tournaments, seasons).

    This class inherits all fields from :class:`Event`:

        - id: Optional[str]
        - event_type: str
        - participants: Dict[str, Entity]
        - time: TimeSpan | None
        - location: Location | None
        - properties: Dict[str, Any]
        - extra: Dict[str, Any]

    and adds a single class-level attribute:

        - frame_type: ClassVar[str] = "event.sports"

    No new runtime fields are introduced; sports-specific structure is
    captured via conventions on `event_type`, `participants`, and
    `properties` (see module-level documentation).
    """

    #: Canonical frame_type string for this frame family.
    frame_type: ClassVar[str] = "event.sports"


__all__ = ["SportsEventFrame"]
