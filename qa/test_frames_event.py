"""
qa/test_frames_event.py

Sanity tests for event-centric frame families.

These tests are intentionally lightweight: they check that the concrete
frame classes for the event family

    - exist and are dataclasses,
    - can be instantiated with minimal, well-formed arguments, and
    - expose a stable frame_type discriminator where applicable.

They do not test any NLG behavior; they only validate the semantic
surface of the event frames.
"""

from dataclasses import is_dataclass

import pytest

from semantics.types import Event

from semantics.event.conflict_war_event_frame import ConflictWarEventFrame
from semantics.event.cultural_event_frame import CulturalEventFrame
from semantics.event.economic_financial_event_frame import (
    EconomicFinancialEventFrame,
)
from semantics.event.election_referendum_event_frame import (
    ElectionReferendumEventFrame,
)
from semantics.event.exploration_expedition_mission_event_frame import (
    ExplorationExpeditionMissionEventFrame,
)
from semantics.event.historical_event_frame import HistoricalEventFrame
from semantics.event.legal_case_event_frame import LegalCaseEventFrame
from semantics.event.life_event_frame import LifeEventFrame
from semantics.event.scientific_technical_milestone_event_frame import (
    ScientificTechnicalMilestoneEventFrame,
)
from semantics.event.sports_event_frame import SportsEventFrame


# ---------------------------------------------------------------------------
# Basic import / dataclass sanity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cls",
    [
        ConflictWarEventFrame,
        CulturalEventFrame,
        EconomicFinancialEventFrame,
        ElectionReferendumEventFrame,
        ExplorationExpeditionMissionEventFrame,
        HistoricalEventFrame,
        LegalCaseEventFrame,
        LifeEventFrame,
        ScientificTechnicalMilestoneEventFrame,
        SportsEventFrame,
    ],
)
def test_event_frames_are_dataclasses(cls) -> None:
    """All concrete event frame classes should be dataclasses."""
    assert is_dataclass(cls), f"{cls.__name__} must be a dataclass"


# ---------------------------------------------------------------------------
# Subclassing of the core Event type
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cls",
    [
        ConflictWarEventFrame,
        LifeEventFrame,
        SportsEventFrame,
    ],
)
def test_event_frames_subclass_core_event(cls) -> None:
    """
    Frames that are thin wrappers over the core Event type should
    subclass semantics.types.Event.
    """
    assert issubclass(cls, Event)
    instance = cls()  # Event supplies defaults, so no args required
    assert isinstance(instance, Event)


# ---------------------------------------------------------------------------
# Frame-type discriminators
# ---------------------------------------------------------------------------


def test_conflict_war_frame_type_constant() -> None:
    frame = ConflictWarEventFrame()
    # Canonical discriminator for this family
    assert getattr(ConflictWarEventFrame, "frame_type") == "event.conflict-event"
    assert frame.frame_type == "event.conflict-event"


def test_cultural_event_frame_type_and_main_event() -> None:
    core = Event()
    frame = CulturalEventFrame(main_event=core)
    assert frame.main_event is core
    assert frame.frame_type == "event.cultural"


def test_economic_financial_event_frame_type_and_main_event() -> None:
    core = Event()
    frame = EconomicFinancialEventFrame(main_event=core)
    assert frame.main_event is core
    assert frame.frame_type == "event.economic"


def test_election_referendum_event_frame_type() -> None:
    frame = ElectionReferendumEventFrame()
    assert frame.frame_type == "event.election"
    # The basic identity fields should exist and be optional
    assert hasattr(frame, "id")
    assert hasattr(frame, "event_kind")


def test_exploration_expedition_mission_event_frame_type_and_default_main_event() -> (
    None
):
    frame = ExplorationExpeditionMissionEventFrame()
    # main_event uses a default factory, so it should always be an Event
    assert isinstance(frame.main_event, Event)
    assert frame.frame_type == "event.exploration"


def test_historical_event_frame_type_and_main_event() -> None:
    core = Event()
    frame = HistoricalEventFrame(main_event=core)
    assert frame.main_event is core
    assert frame.frame_type == "event.historical"


def test_legal_case_event_frame_type_and_main_event() -> None:
    core = Event()
    frame = LegalCaseEventFrame(main_event=core)
    assert frame.main_event is core
    assert frame.frame_type == "event.legal_case"


def test_life_event_frame_type_and_alias_properties() -> None:
    frame = LifeEventFrame()
    assert frame.frame_type == "event.life"
    # The thin wrapper should still behave like an Event
    assert isinstance(frame, Event)
    # Convenience aliases should be present
    assert hasattr(frame, "timespan")
    assert hasattr(frame, "place")


def test_scientific_technical_milestone_event_frame_type() -> None:
    frame = ScientificTechnicalMilestoneEventFrame()
    assert frame.frame_type == "event.scientific_milestone"
    # main_event is optional but should be present as an attribute
    assert hasattr(frame, "main_event")


def test_sports_event_frame_type_and_subclassing() -> None:
    frame = SportsEventFrame()
    assert SportsEventFrame.frame_type == "event.sports"
    assert frame.frame_type == "event.sports"
    assert isinstance(frame, Event)
