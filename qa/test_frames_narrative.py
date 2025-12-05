"""
qa/test_frames_narrative.py

Smoke tests for the narrative / aggregate frame dataclasses.

These tests are intentionally light-weight and do not depend on any
particular NLG engine implementation. Their purpose is to verify that:

- Narrative frame classes can be instantiated with minimal, realistic data.
- Canonical frame_type constants are wired as documented.
- Key container fields (entries / phases / items / units) default to empty
  lists or dicts and can be populated without errors.

The frames covered here correspond to the “Temporal / narrative / aggregate”
families in `docs/FRAMES_NARRATIVE.md` and `semantics/all_frames.py`:

    - TimelineChronologyFrame                (aggregate.timeline)
    - CareerSeasonCampaignSummaryFrame       (aggregate.career_summary)
    - DevelopmentEvolutionFrame              (aggregate.development)
    - ReceptionImpactFrame                   (aggregate.reception)
    - StructureOrganizationFrame             (narr.structure-organization)
    - ComparisonSetContrastFrame             (narr.comparison-set-contrast)
    - ListEnumerationFrame                   (aggregate.list)
"""

from __future__ import annotations

from dataclasses import asdict

from semantics.types import Entity, Event, TimeSpan, Location
from semantics.narrative.timeline_chronology_frame import (
    TimelineChronologyFrame,
    TimelineEntry,
)
from semantics.narrative.career_season_campaign_summary_frame import (
    CareerSeasonCampaignSummaryFrame,
    CareerPhase,
)
from semantics.narrative.development_evolution_frame import (
    DevelopmentEvolutionFrame,
    DevelopmentStage,
)
from semantics.narrative.reception_impact_frame import (
    ReceptionImpactFrame,
    ReceptionItem,
    ImpactDomain,
)
from semantics.narrative.structure_organization_frame import (
    StructureOrganizationFrame,
    OrganizationalUnitNode,
)
from semantics.narrative.comparison_set_contrast_frame import (
    ComparisonSetContrastFrame,
    ComparisonItem,
)
from semantics.narrative.list_enumeration_frame import (
    ListEnumerationFrame,
    ListItem,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_sample_person() -> Entity:
    return Entity(id="P1", name="Sample Person", human=True, entity_type="person")


def _make_sample_city() -> Entity:
    return Entity(id="C1", name="Sample City", entity_type="city")


def _make_sample_country() -> Entity:
    return Entity(id="C2", name="Sample Country", entity_type="country")


def _make_sample_work() -> Entity:
    return Entity(id="W1", name="Sample Work", entity_type="creative_work")


def _make_sample_event(event_id: str, event_type: str, year: int) -> Event:
    return Event(
        id=event_id,
        event_type=event_type,
        participants={"subject": _make_sample_person()},
        time=TimeSpan(start_year=year),
        location=Location(id="L1", name="Sample Location"),
    )


# ---------------------------------------------------------------------------
# Timeline / chronology frame
# ---------------------------------------------------------------------------


def test_timeline_chronology_basic_construction() -> None:
    subject = _make_sample_person()

    birth = _make_sample_event("E_birth", "birth", 1980)
    award = _make_sample_event("E_award", "award", 2010)

    entries = [
        TimelineEntry(event=birth, label="Born", phase="early_life", salience=1.0),
        TimelineEntry(
            event=award, label="Receives major award", phase="career", salience=0.8
        ),
    ]

    frame = TimelineChronologyFrame(
        subject=subject,
        overall_span=TimeSpan(start_year=1980, end_year=2015),
        entries=entries,
        ordering="chronological",
        grouping_hint="by_phase",
    )

    # Basic invariants
    assert frame.frame_type == "aggregate.timeline"
    assert frame.subject is subject
    assert len(frame.entries) == 2
    assert frame.entries[0].event.id == "E_birth"
    assert frame.entries[1].phase == "career"

    # Ensure frame is dataclass-serializable
    data = asdict(frame)
    assert data["frame_type"] == "aggregate.timeline"
    assert isinstance(data["entries"], list)


# ---------------------------------------------------------------------------
# Career / season / campaign summary frame
# ---------------------------------------------------------------------------


def test_career_season_campaign_summary_basic() -> None:
    span = TimeSpan(start_year=2000, end_year=2020)

    early_phase = CareerPhase(
        label="early_career",
        span=TimeSpan(start_year=2000, end_year=2005),
        key_events=[_make_sample_event("E1", "debut", 2000)],
        metrics={"goals": 10},
    )
    prime_phase = CareerPhase(
        label="prime",
        span=TimeSpan(start_year=2006, end_year=2015),
        key_events=[_make_sample_event("E2", "championship_win", 2010)],
        metrics={"goals": 80},
    )

    frame = CareerSeasonCampaignSummaryFrame(
        subject_id="P1",
        domain="sports",
        span=span,
        phases=[early_phase, prime_phase],
        metrics={"goals": 100, "appearances": 300},
        headline="Prolific forward over two decades",
    )

    assert frame.frame_type == "aggregate.career_summary"
    assert frame.subject_id == "P1"
    assert frame.domain == "sports"
    assert len(frame.phases) == 2
    assert frame.phases[1].metrics["goals"] == 80
    assert frame.metrics["goals"] == 100

    data = asdict(frame)
    assert data["frame_type"] == "aggregate.career_summary"
    assert isinstance(data["phases"], list)


# ---------------------------------------------------------------------------
# Development / evolution frame
# ---------------------------------------------------------------------------


def test_development_evolution_basic() -> None:
    subject = _make_sample_city()

    stage_1 = DevelopmentStage(
        label="founding_and_early_growth",
        time_span=TimeSpan(start_year=1800, end_year=1850),
        summary="Founded as a small trading post.",
        key_events=[_make_sample_event("E1", "founding", 1800)],
        drivers=["trade", "river_transport"],
    )
    stage_2 = DevelopmentStage(
        label="industrialization",
        time_span=TimeSpan(start_year=1850, end_year=1950),
        summary="Industrial growth and urbanization.",
        key_events=[_make_sample_event("E2", "factory_built", 1880)],
        drivers=["railways", "manufacturing"],
    )

    frame = DevelopmentEvolutionFrame(
        subject=subject,
        overall_time_span=TimeSpan(start_year=1800, end_year=2000),
        stages=[stage_1, stage_2],
        key_transitions=[_make_sample_event("E3", "port_expansion", 1900)],
        global_drivers=["industrialization", "globalization"],
        global_outcomes=["major_industrial_center"],
        attributes={"population_growth_factor": 20.0},
        extra={"source": "Sample dataset"},
    )

    assert frame.frame_type == "aggregate.development"
    assert frame.subject is subject
    assert len(frame.stages) == 2
    assert frame.stages[0].label == "founding_and_early_growth"
    assert "industrialization" in frame.global_drivers
    assert frame.attributes["population_growth_factor"] == 20.0

    data = asdict(frame)
    assert data["frame_type"] == "aggregate.development"
    assert isinstance(data["stages"], list)


# ---------------------------------------------------------------------------
# Reception / impact frame
# ---------------------------------------------------------------------------


def test_reception_impact_basic() -> None:
    work = _make_sample_work()

    critic = _make_sample_person()
    critic.name = "Sample Critic"

    reception_item = ReceptionItem(
        source=critic,
        aspect="critical_reception",
        summary="Widely acclaimed by critics.",
        representative_quote="A landmark work in its field.",
        time_span=TimeSpan(start_year=2005),
        attributes={"rating": 4.8},
    )

    impact_domain = ImpactDomain(
        domain_label="film",
        summary="Influenced a generation of filmmakers.",
        examples=["Later directors cited it as a major influence."],
        metrics={"citations": 120, "remakes": 2},
    )

    award_event = Event(
        id="E_award",
        event_type="award",
        participants={"subject": work},
        time=TimeSpan(start_year=2006),
        properties={"award_name": "Sample Award"},
    )

    frame = ReceptionImpactFrame(
        subject_id=work.id,
        critical_reception=[reception_item],
        public_reception=[],
        impact_domains=[impact_domain],
        metrics={"box_office": 100_000_000},
        awards=[award_event],
        extra={"notes": "Test frame"},
    )

    assert frame.frame_type == "aggregate.reception"
    assert frame.subject_id == "W1"
    assert len(frame.critical_reception) == 1
    assert frame.critical_reception[0].attributes["rating"] == 4.8
    assert frame.impact_domains[0].domain_label == "film"
    assert frame.metrics["box_office"] == 100_000_000
    assert frame.awards[0].event_type == "award"

    data = asdict(frame)
    assert data["frame_type"] == "aggregate.reception"
    assert isinstance(data["impact_domains"], list)


# ---------------------------------------------------------------------------
# Structure / organization frame
# ---------------------------------------------------------------------------


def test_structure_organization_basic() -> None:
    main_entity = _make_sample_country()

    unit_exec = OrganizationalUnitNode(
        key="executive",
        entity=Entity(id="U1", name="Executive Branch"),
        parent_key=None,
        role_labels=["executive"],
        attributes={"powers": ["implements_laws"]},
    )

    unit_leg = OrganizationalUnitNode(
        key="legislature",
        entity=Entity(id="U2", name="Legislature"),
        parent_key=None,
        role_labels=["legislative"],
        attributes={"powers": ["passes_laws"]},
    )

    frame = StructureOrganizationFrame(
        main_entity=main_entity,
        structure_type_lemmas=["parliamentary_republic"],
        unit_index_key="key",
        units=[unit_exec, unit_leg],
        key_positions={
            "head_of_state": [Entity(id="P_head", name="Head of State", human=True)],
        },
        attributes={"chambers": 2, "is_bicameral": True},
    )

    assert frame.frame_type == "narr.structure-organization"
    assert frame.main_entity is main_entity
    assert len(frame.units) == 2
    assert frame.units[0].key == "executive"
    assert frame.key_positions["head_of_state"][0].human is True
    assert frame.attributes["is_bicameral"] is True

    data = asdict(frame)
    assert data["frame_type"] == "narr.structure-organization"
    assert isinstance(data["units"], list)


# ---------------------------------------------------------------------------
# Comparison / contrast frame
# ---------------------------------------------------------------------------


def test_comparison_set_contrast_basic() -> None:
    city_a = Entity(id="C_A", name="City A", entity_type="city")
    city_b = Entity(id="C_B", name="City B", entity_type="city")
    city_c = Entity(id="C_C", name="City C", entity_type="city")

    items = [
        ComparisonItem(entity=city_a, metric_values={"population": 1_000_000}),
        ComparisonItem(entity=city_b, metric_values={"population": 500_000}),
        ComparisonItem(entity=city_c, metric_values={"population": 2_000_000}),
    ]

    frame = ComparisonSetContrastFrame(
        items=items,
        focus_entity=city_c,
        metrics={
            "population": {
                "unit": "inhabitants",
                "description": "City population",
            }
        },
        primary_metric_id="population",
        order_direction="descending",
        comparison_type="ranking",
        scope_locations=[Location(id="L_country", name="Sample Country")],
        attributes={"source": "Sample statistics"},
    )

    assert ComparisonSetContrastFrame.frame_type == "narr.comparison-set-contrast"
    assert len(frame.items) == 3
    assert frame.focus_entity is city_c
    assert frame.primary_metric_id == "population"
    assert frame.order_direction == "descending"
    assert frame.items[2].entity.name == "City C"

    data = asdict(frame)
    # frame_type is a ClassVar, not in instance dict; check via class
    assert ComparisonSetContrastFrame.frame_type == "narr.comparison-set-contrast"
    assert isinstance(data["items"], list)


# ---------------------------------------------------------------------------
# List / enumeration frame
# ---------------------------------------------------------------------------


def test_list_enumeration_basic() -> None:
    team = Entity(id="T1", name="Sample Team", entity_type="sports_team")

    items = [
        ListItem(entity=Entity(id="P1", name="Player One", human=True), label=None),
        ListItem(entity=Entity(id="P2", name="Player Two", human=True), label=None),
        ListItem(entity=None, label="Other notable players"),
    ]

    frame = ListEnumerationFrame(
        subject_id=team.id,
        list_kind="notable_players",
        ordering="by_role",
        scope="current",
        items=items,
        preferred_realization="include",
        extra={"notes": "Test enumeration"},
    )

    assert ListEnumerationFrame.frame_type == "aggregate.list"
    assert frame.subject_id == "T1"
    assert len(frame.items) == 3
    assert frame.items[0].entity.name == "Player One"
    assert frame.list_kind == "notable_players"
    assert frame.ordering == "by_role"

    data = asdict(frame)
    # frame_type is a ClassVar, so not in instance dict; verify at class level
    assert ListEnumerationFrame.frame_type == "aggregate.list"
    assert isinstance(data["items"], list)


# ---------------------------------------------------------------------------
# Sanity check: default empties
# ---------------------------------------------------------------------------


def test_default_containers_are_empty_and_independent() -> None:
    """
    Ensure that list / dict fields default to empty containers and that
    they are not shared across instances.
    """
    f1 = ListEnumerationFrame()
    f2 = ListEnumerationFrame()

    assert f1.items == []
    assert f2.items == []
    assert f1.items is not f2.items

    c1 = CareerSeasonCampaignSummaryFrame()
    c2 = CareerSeasonCampaignSummaryFrame()

    assert c1.phases == []
    assert c2.phases == []
    assert c1.phases is not c2.phases

    d1 = DevelopmentEvolutionFrame(subject=_make_sample_city())
    d2 = DevelopmentEvolutionFrame(subject=_make_sample_city())

    assert d1.stages == []
    assert d2.stages == []
    assert d1.stages is not d2.stages
