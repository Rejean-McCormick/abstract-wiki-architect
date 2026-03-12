# tests/unit/planning/test_frame_to_plan.py
from __future__ import annotations

from copy import deepcopy

from app.core.domain.planning.planned_sentence import PlannedSentence
from discourse.planner import plan_biography, plan_generic, select_construction_id


def _frame(frame_type: str, **overrides):
    payload = {"frame_type": frame_type}
    payload.update(overrides)
    return payload


def _construction_ids(plans: list[PlannedSentence]) -> list[str]:
    return [plan.construction_id for plan in plans]


def _order_indexes(plans: list[PlannedSentence]) -> list[int]:
    return [int(plan.metadata["order_index"]) for plan in plans]


def test_select_construction_id_prefers_explicit_frame_override():
    frame = _frame(
        "achievement",
        construction_id="topic_comment_eventive",
    )

    result = select_construction_id(frame, domain="generic")

    assert result == "topic_comment_eventive"


def test_select_construction_id_emits_bio_lead_identity_only_when_opted_in():
    frame = _frame("definition", use_bio_lead=True)

    lead_result = select_construction_id(
        frame,
        domain="bio",
        is_lead_sentence=True,
    )
    non_lead_result = select_construction_id(
        frame,
        domain="bio",
        is_lead_sentence=False,
    )

    assert lead_result == "bio_lead_identity"
    assert non_lead_result == "copula_equative_simple"


def test_plan_biography_orders_by_explicit_priority_then_bio_policy():
    frames = [
        _frame(
            "career",
            id="F-career",
            entity_id="Q1",
        ),
        _frame(
            "definition",
            id="F-definition",
            entity_id="Q1",
        ),
        _frame(
            "award",
            id="F-award",
            entity_id="Q1",
            priority=-10,
        ),
    ]

    plans = plan_biography(frames, lang_code="en")

    assert all(isinstance(plan, PlannedSentence) for plan in plans)
    assert _construction_ids(plans) == [
        "ditransitive_event",
        "copula_equative_simple",
        "intransitive_event",
    ]
    assert _order_indexes(plans) == [0, 1, 2]
    assert [plan.metadata["frame_type"] for plan in plans] == [
        "award",
        "definition",
        "career",
    ]


def test_plan_biography_reuses_topic_anchor_only_for_matching_entity():
    frames = [
        _frame(
            "definition",
            id="F-definition",
            entity_id="Q_TOPIC",
            use_bio_lead=True,
        ),
        _frame(
            "birth",
            id="F-birth",
            entity_id="Q_TOPIC",
        ),
        _frame(
            "award",
            id="F-award",
            entity_id="Q_OTHER",
        ),
    ]

    plans = plan_biography(frames, lang_code="en")

    assert [plan.topic_entity_id for plan in plans] == [
        "Q_TOPIC",
        "Q_TOPIC",
        None,
    ]
    assert plans[0].metadata["is_lead_sentence"] is True
    assert plans[1].metadata["is_lead_sentence"] is False
    assert plans[2].metadata["is_lead_sentence"] is False


def test_plan_generic_preserves_input_order_for_non_biography_domain():
    frames = [
        _frame(
            "location",
            id="F-loc",
            entity_id="Q1",
        ),
        _frame(
            "classification",
            id="F-class",
            entity_id="Q1",
        ),
        _frame(
            "achievement",
            id="F-ach",
            entity_id="Q2",
        ),
    ]

    plans = plan_generic(frames, lang_code="en", domain="generic")

    assert _construction_ids(plans) == [
        "copula_locative",
        "copula_equative_classification",
        "transitive_event",
    ]
    assert [plan.metadata["frame_type"] for plan in plans] == [
        "location",
        "classification",
        "achievement",
    ]
    assert _order_indexes(plans) == [0, 1, 2]


def test_plan_generic_auto_routes_biography_like_frames_to_biography_policy():
    frames = [
        _frame(
            "career",
            id="F-career",
            entity_id="Q1",
        ),
        _frame(
            "definition",
            id="F-definition",
            entity_id="Q1",
        ),
    ]

    plans = plan_generic(frames, lang_code="en", domain="auto")

    assert _construction_ids(plans) == [
        "copula_equative_simple",
        "intransitive_event",
    ]
    assert [plan.metadata["planner_domain"] for plan in plans] == ["bio", "bio"]


def test_plan_builds_metadata_defaults_and_preserves_input_mappings():
    frame = _frame(
        "achievement",
        id="F-1",
        entity_id="Q1",
        metadata={"source": "fixture"},
        generation_options={"style": "formal"},
    )
    original = deepcopy(frame)

    [plan] = plan_generic([frame], lang_code="EN", domain="generic")

    assert plan.lang_code == "en"
    assert plan.focus_role == "patient"
    assert plan.discourse_mode == "declarative"
    assert plan.source_frame_ids == ("F-1",)
    assert dict(plan.generation_options) == {"style": "formal"}

    metadata = dict(plan.metadata)
    assert metadata["source"] == "fixture"
    assert metadata["frame_type"] == "achievement"
    assert metadata["planner_domain"] == "generic"
    assert metadata["planner_module"] == "discourse.planner"
    assert metadata["order_index"] == 0
    assert metadata["main_entity_id"] == "Q1"

    assert frame == original


def test_plan_uses_source_frame_ids_when_present_and_deduplicates_them():
    frame = _frame(
        "location",
        source_frame_ids=["F-1", "F-2", "F-1", "F-2", "F-3"],
        entity_id="Q1",
    )

    [plan] = plan_generic([frame], lang_code="en", domain="generic")

    assert plan.source_frame_ids == ("F-1", "F-2", "F-3")


def test_plan_generic_is_deterministic_for_same_input():
    frames = [
        _frame(
            "definition",
            id="F-definition",
            entity_id="Q1",
            metadata={"source": "fixture"},
        ),
        _frame(
            "birth",
            id="F-birth",
            entity_id="Q1",
        ),
    ]

    first = plan_generic(deepcopy(frames), lang_code="en", domain="auto")
    second = plan_generic(deepcopy(frames), lang_code="en", domain="auto")

    assert [plan.to_dict() for plan in first] == [plan.to_dict() for plan in second]