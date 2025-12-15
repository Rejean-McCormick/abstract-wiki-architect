# semantics\event\exploration_expedition_mission_event_frame.py
"""
semantics/event/exploration_expedition_mission_event_frame.py
-------------------------------------------------------------

Semantic frame for exploration, expeditions, and missions.

This module provides a typed wrapper around the generic
:class:`semantics.types.Event` to represent:

    - Space missions (e.g., Apollo 11)
    - Geographic expeditions (e.g., Lewis and Clark)
    - Deep sea exploration
    - Mountaineering expeditions

It organizes participants into roles like crew, sponsors, and vessels,
and handles destinations and outcomes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, List, Optional

from semantics.types import Entity, Event


@dataclass
class ExplorationExpeditionMissionEventFrame:
    """
    Semantic frame for exploration, expeditions, and missions.

    frame_type:
        Stable label for routing / planning. Defaults to "event.exploration".

    main_event:
        The underlying :class:`Event` instance. In this frame, it defaults
        to a new Event() if not provided, allowing for flexible instantiation.

    Participants
    ------------
    crew:
        The individuals or groups physically undertaking the mission.

    sponsors:
        Organizations or nations funding or directing the mission (e.g., NASA,
        Royal Geographical Society).

    vessels:
        Vehicles or ships used (e.g., "Apollo 11 Command Module", "HMS Beagle").

    destinations:
        The specific targets of the exploration (e.g., "Moon", "South Pole").

    """

    # ClassVar ensures this is not treated as an init argument
    frame_type: ClassVar[str] = "event.exploration"

    # Core event with default factory (REQUIRED by tests to allow empty init)
    main_event: Event = field(default_factory=Event)

    label: Optional[str] = None

    # Participants
    subject_entities: List[Entity] = field(default_factory=list)
    crew: List[Entity] = field(default_factory=list)
    sponsors: List[Entity] = field(default_factory=list)
    vessels: List[Entity] = field(default_factory=list)
    destinations: List[Entity] = field(default_factory=list)

    # Extensibility
    attributes: Dict[str, Any] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)


__all__ = ["ExplorationExpeditionMissionEventFrame"]
