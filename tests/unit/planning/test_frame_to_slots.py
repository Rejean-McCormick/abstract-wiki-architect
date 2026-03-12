# tests/unit/planning/test_frame_to_slots.py
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field

import pytest

from app.core.bridges.frame_to_slots import (
    FrameToSlotsBridge,
    InvalidSlotMapError,
    MissingRequiredRoleError,
    UnsupportedConstructionError,
    frame_to_slots,
)
from app.core.domain.models import Frame


@dataclass
class BioFrameObject:
    frame_type: str = "bio"
    main_entity: dict = field(default_factory=dict)
    primary_profession_lemmas: list[str] = field(default_factory=list)
    nationality_lemmas: list[str] = field(default_factory=list)
    properties: dict = field(default_factory=dict)
    meta: dict = field(default_factory=dict)


def _bio_frame_dict() -> dict:
    return {
        "frame_type": "bio",
        "main_entity": {
            "id": "Q7186",
            "name": "Marie Curie",
            "gender": "female",
            "human": True,
        },
        "primary_profession_lemmas": ["physicist"],
        "nationality_lemmas": ["polish"],
        "properties": {
            "time": "1867-11-07",
        },
    }


def _transitive_event_frame() -> dict:
    return {
        "frame_type": "event",
        "event": {
            "event_type": "discover",
            "participants": {
                "agent": {"id": "Q7186", "name": "Marie Curie", "human": True},
                "object": {"id": "Q36963", "name": "polonium"},
            },
            "time": "1898-07-01",
            "location": {
                "id": "Q90",
                "name": "Paris",
                "country_code": "fr",
                "kind": "city",
            },
        },
    }


def test_supports_reports_only_explicit_handlers() -> None:
    bridge = FrameToSlotsBridge()

    assert bridge.supports("copula_equative_simple") is True
    assert bridge.supports("relative_clause_object_gap") is True
    assert bridge.supports("unlisted_custom_construction") is False


def test_functional_entrypoint_builds_classification_slot_map_from_dict() -> None:
    slot_map = frame_to_slots(
        _bio_frame_dict(),
        construction_id="copula_equative_classification",
    )

    assert slot_map["subject"] == {
        "label": "Marie Curie",
        "entity_id": "Q7186",
        "features": {
            "gender": "female",
            "human": True,
        },
    }
    assert slot_map["profession"] == {
        "lemma": "physicist",
        "pos": "NOUN",
        "source": "frame",
    }
    assert slot_map["nationality"] == {
        "lemma": "polish",
        "pos": "ADJ",
        "source": "frame",
    }
    assert slot_map["predicate_nominal"] == {
        "role": "profession_plus_nationality",
        "profession": {
            "lemma": "physicist",
            "pos": "NOUN",
            "source": "frame",
        },
        "nationality": {
            "lemma": "polish",
            "pos": "ADJ",
            "source": "frame",
        },
    }
    assert slot_map["time"] == {
        "start_year": 1867,
        "start_month": 11,
        "start_day": 7,
    }


def test_build_slot_map_accepts_pydantic_frame_model() -> None:
    frame = Frame(
        frame_type="bio",
        main_entity={
            "id": "Q7186",
            "name": "Marie Curie",
            "gender": "female",
            "human": True,
        },
        primary_profession_lemmas=["physicist"],
        nationality_lemmas=["polish"],
    )

    slot_map = FrameToSlotsBridge().build_slot_map(
        frame,
        construction_id="copula_equative_simple",
    )

    assert slot_map["subject"]["label"] == "Marie Curie"
    assert slot_map["predicate_nominal"]["role"] == "profession_plus_nationality"
    assert slot_map["profession"]["lemma"] == "physicist"
    assert slot_map["nationality"]["lemma"] == "polish"


def test_build_slot_map_accepts_dataclass_like_frame_object() -> None:
    frame = BioFrameObject(
        main_entity={
            "id": "Q7186",
            "name": "Marie Curie",
            "gender": "female",
            "human": True,
        },
        primary_profession_lemmas=["physicist"],
        nationality_lemmas=["polish"],
        properties={"time": 1867},
    )

    slot_map = FrameToSlotsBridge().build_slot_map(
        frame,
        construction_id="copula_equative_classification",
    )

    assert slot_map["subject"]["entity_id"] == "Q7186"
    assert slot_map["profession"]["lemma"] == "physicist"
    assert slot_map["nationality"]["lemma"] == "polish"
    assert slot_map["time"] == {"start_year": 1867}


def test_transitive_event_extracts_subject_object_predicate_and_common_modifiers() -> None:
    slot_map = frame_to_slots(
        _transitive_event_frame(),
        construction_id="transitive_event",
    )

    assert slot_map["subject"] == {
        "label": "Marie Curie",
        "entity_id": "Q7186",
        "features": {"human": True},
    }
    assert slot_map["object"] == {
        "label": "polonium",
        "entity_id": "Q36963",
    }
    assert slot_map["predicate"] == {
        "lemma": "discover",
        "pos": "VERB",
        "source": "frame",
        "event_type": "discover",
    }
    assert slot_map["time"] == {
        "start_year": 1898,
        "start_month": 7,
        "start_day": 1,
    }
    assert slot_map["location"] == {
        "label": "Paris",
        "entity_id": "Q90",
        "entity_type": "city",
        "country_code": "FR",
        "location_type": "city",
    }


def test_missing_required_role_raises_stable_error_for_transitive_event() -> None:
    frame = {
        "frame_type": "event",
        "event": {
            "event_type": "discover",
            "participants": {
                "agent": {"name": "Marie Curie"},
            },
        },
    }

    with pytest.raises(MissingRequiredRoleError, match="subject|object"):
        frame_to_slots(frame, construction_id="transitive_event")


def test_unknown_construction_falls_back_to_generic_semantic_role_extraction() -> None:
    frame = {
        "frame_type": "attribute",
        "subject": {"name": "Marie Curie"},
        "predicate_adjective": "brilliant",
        "properties": {"time": "1903"},
    }

    slot_map = frame_to_slots(
        frame,
        construction_id="experimental_unknown_construction",
    )

    assert slot_map == {
        "subject": {"label": "Marie Curie"},
        "predicate_adjective": {
            "lemma": "brilliant",
            "pos": "ADJ",
            "source": "frame",
        },
        "time": {"start_year": 1903},
    }


def test_unknown_construction_with_no_meaningful_content_raises() -> None:
    frame = {
        "frame_type": "emptyish",
        "properties": {},
        "meta": {},
        "extra": {},
    }

    with pytest.raises(
        UnsupportedConstructionError,
        match="No frame-to-slot mapping rule produced content",
    ):
        frame_to_slots(frame, construction_id="experimental_unknown_construction")


def test_reserved_plan_level_slot_names_are_rejected() -> None:
    bridge = FrameToSlotsBridge(
        custom_handlers={
            "custom_reserved_key": lambda _frame: {
                "construction_id": "should_not_be_a_slot",
                "subject": {"label": "Marie Curie"},
            }
        }
    )

    with pytest.raises(
        InvalidSlotMapError,
        match="Reserved plan-level field 'construction_id'",
    ):
        bridge.build_slot_map({}, construction_id="custom_reserved_key")


def test_finalize_compacts_empty_values_but_preserves_zero_and_false() -> None:
    bridge = FrameToSlotsBridge(
        custom_handlers={
            "custom_compaction": lambda _frame: {
                "subject": {
                    "label": "Marie Curie",
                    "features": {
                        "human": False,
                        "person": 0,
                        "blank": "   ",
                    },
                    "extra": {
                        "empty_note": "",
                        "keep_zero": 0,
                    },
                },
                "comment": "   ",
                "quantity": 0,
            }
        }
    )

    slot_map = bridge.build_slot_map({}, construction_id="custom_compaction")

    assert slot_map == {
        "subject": {
            "label": "Marie Curie",
            "features": {
                "human": False,
                "person": 0,
            },
            "extra": {
                "keep_zero": 0,
            },
        },
        "quantity": 0,
    }


def test_bridge_is_deterministic_and_does_not_mutate_input_or_share_nested_state() -> None:
    bridge = FrameToSlotsBridge()
    frame = _bio_frame_dict()
    original = deepcopy(frame)

    first = bridge.build_slot_map(
        frame,
        construction_id="copula_equative_classification",
    )
    second = bridge.build_slot_map(
        frame,
        construction_id="copula_equative_classification",
    )

    assert first == second
    assert frame == original

    # The returned structures should be independent from one another.
    first["subject"]["label"] = "Changed"
    first["profession"]["lemma"] = "chemist"

    assert second["subject"]["label"] == "Marie Curie"
    assert second["profession"]["lemma"] == "physicist"