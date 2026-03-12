# tests/unit/planning/test_construction_plan.py
from __future__ import annotations

from types import MappingProxyType

import pytest

from app.core.domain.planning.construction_plan import ConstructionPlan


def test_construction_plan_normalizes_required_and_optional_fields():
    plan = ConstructionPlan(
        construction_id="  copula_equative_classification  ",
        lang_code="  eng  ",
        slot_map={"subject": {"id": "Q1", "name": "Marie Curie"}},
        generation_options={"register": "formal"},
        topic_entity_id="  Q1  ",
        focus_role="  predicate_nominal  ",
    )

    assert plan.construction_id == "copula_equative_classification"
    assert plan.lang_code == "eng"
    assert plan.topic_entity_id == "Q1"
    assert plan.focus_role == "predicate_nominal"
    assert plan.slot_keys == ("subject",)


def test_blank_optional_discourse_fields_are_normalized_to_none():
    plan = ConstructionPlan(
        construction_id="copula_equative_classification",
        lang_code="eng",
        slot_map={"subject": {"id": "Q1"}},
        topic_entity_id="   ",
        focus_role="",
    )

    assert plan.topic_entity_id is None
    assert plan.focus_role is None


def test_rejects_reserved_plan_level_names_inside_slot_map():
    with pytest.raises(ValueError, match="reserved plan-level field"):
        ConstructionPlan(
            construction_id="copula_equative_classification",
            lang_code="eng",
            slot_map={
                "subject": {"id": "Q1"},
                "construction_id": "should_not_be_a_slot",
            },
        )


def test_rejects_non_string_or_empty_slot_names():
    with pytest.raises(TypeError, match="slot_map keys must be strings"):
        ConstructionPlan(
            construction_id="copula_equative_classification",
            lang_code="eng",
            slot_map={1: "bad-key"},  # type: ignore[arg-type]
        )

    with pytest.raises(ValueError, match="empty slot name"):
        ConstructionPlan(
            construction_id="copula_equative_classification",
            lang_code="eng",
            slot_map={"   ": "bad-key"},
        )


def test_frozen_internal_state_does_not_expose_mutable_jsonish_objects():
    plan = ConstructionPlan(
        construction_id="copula_equative_classification",
        lang_code="eng",
        slot_map={
            "subject": {"id": "Q1", "name": "Marie Curie"},
            "predicates": ["scientist", {"modifiers": ["famous", "French"]}],
        },
        generation_options={"style": ["formal"]},
        lexical_bindings={"predicate_nominal": {"lemma": "scientist", "pos": "N"}},
        provenance={"pipeline": ["planner", "resolver"]},
        metadata={"wrapper_construction_id": "topic_comment_copular"},
    )

    assert isinstance(plan.slot_map, MappingProxyType)
    assert isinstance(plan.slot_map["subject"], MappingProxyType)
    assert isinstance(plan.slot_map["predicates"], tuple)
    assert isinstance(plan.slot_map["predicates"][1], MappingProxyType)
    assert isinstance(plan.slot_map["predicates"][1]["modifiers"], tuple)

    assert isinstance(plan.generation_options, MappingProxyType)
    assert isinstance(plan.generation_options["style"], tuple)

    with pytest.raises(TypeError):
        plan.slot_map["new_slot"] = "x"  # type: ignore[index]

    with pytest.raises(TypeError):
        plan.slot_map["subject"]["name"] = "Changed"  # type: ignore[index]


def test_to_dict_round_trips_and_omits_empty_optional_mappings_by_default():
    plan = ConstructionPlan(
        construction_id="copula_equative_classification",
        lang_code="eng",
        slot_map={
            "subject": {"id": "Q1", "name": "Marie Curie"},
            "predicate_nominal": ["physicist", "chemist"],
        },
        generation_options={"register": "formal"},
    )

    compact = plan.to_dict()
    full = plan.to_dict(include_empty=True)

    assert compact == {
        "construction_id": "copula_equative_classification",
        "lang_code": "eng",
        "slot_map": {
            "subject": {"id": "Q1", "name": "Marie Curie"},
            "predicate_nominal": ["physicist", "chemist"],
        },
        "generation_options": {"register": "formal"},
    }

    assert full["lexical_bindings"] == {}
    assert full["provenance"] == {}
    assert full["metadata"] == {}

    rebuilt = ConstructionPlan.from_dict(
        {
            **full,
            "unknown_envelope_key": "ignored",
        }
    )

    assert rebuilt == plan
    assert rebuilt.to_dict(include_empty=True) == full


def test_from_dict_requires_mapping_like_input():
    with pytest.raises(TypeError, match="expects a mapping"):
        ConstructionPlan.from_dict(["not", "a", "mapping"])  # type: ignore[arg-type]


def test_with_slot_helpers_return_new_instances_without_mutating_original():
    original = ConstructionPlan(
        construction_id="copula_equative_classification",
        lang_code="eng",
        slot_map={
            "subject": {"id": "Q1", "name": "Marie Curie"},
            "predicate_nominal": "scientist",
        },
        generation_options={"register": "formal"},
    )

    with_one_extra = original.with_slot("nationality", "Polish")
    with_many = with_one_extra.with_slots(copula="is", tense="present")
    without_predicate = with_many.without_slot("predicate_nominal")

    assert "nationality" not in original
    assert "copula" not in original
    assert "predicate_nominal" in original

    assert with_one_extra["nationality"] == "Polish"
    assert with_many["copula"] == "is"
    assert with_many["tense"] == "present"
    assert "predicate_nominal" not in without_predicate
    assert without_predicate["nationality"] == "Polish"

    assert original["predicate_nominal"] == "scientist"


def test_with_slot_rejects_blank_or_reserved_slot_names():
    plan = ConstructionPlan(
        construction_id="copula_equative_classification",
        lang_code="eng",
        slot_map={"subject": {"id": "Q1"}},
    )

    with pytest.raises(ValueError, match="non-empty string"):
        plan.with_slot("   ", "bad")

    with pytest.raises(ValueError, match="reserved plan-level field"):
        plan.with_slot("construction_id", "bad")


def test_mapping_merge_helpers_preserve_existing_state_and_merge_updates():
    plan = ConstructionPlan(
        construction_id="copula_equative_classification",
        lang_code="eng",
        slot_map={"subject": {"id": "Q1"}},
        generation_options={"register": "formal"},
        lexical_bindings={"predicate_nominal": {"lemma": "scientist"}},
        provenance={"builder": "frame_to_slots"},
        metadata={"wrapper_construction_id": "topic_comment_copular"},
    )

    updated = (
        plan.with_generation_options({"voice": "active"}, register="neutral")
        .with_lexical_bindings({"nationality": {"lemma": "polish"}}, copula={"lemma": "be"})
        .with_provenance({"selector": "construction_registry"}, phase="unit_test")
        .with_metadata({"base_construction_id": "copula_equative_classification"}, batch="6")
        .with_discourse(topic_entity_id="Q1", focus_role="predicate_nominal")
    )

    assert plan.generation_options["register"] == "formal"
    assert updated.generation_options == {
        "register": "neutral",
        "voice": "active",
    }

    assert updated.lexical_bindings["predicate_nominal"]["lemma"] == "scientist"
    assert updated.lexical_bindings["nationality"]["lemma"] == "polish"
    assert updated.lexical_bindings["copula"]["lemma"] == "be"

    assert updated.provenance["builder"] == "frame_to_slots"
    assert updated.provenance["selector"] == "construction_registry"
    assert updated.provenance["phase"] == "unit_test"

    assert updated.metadata["wrapper_construction_id"] == "topic_comment_copular"
    assert updated.metadata["base_construction_id"] == "copula_equative_classification"
    assert updated.metadata["batch"] == "6"

    assert updated.topic_entity_id == "Q1"
    assert updated.focus_role == "predicate_nominal"


def test_wrapper_properties_summary_and_required_slot_checks():
    wrapped = ConstructionPlan(
        construction_id="topic_comment_copular",
        lang_code="eng",
        slot_map={
            "topic": {"id": "Q1", "name": "Marie Curie"},
            "comment": {"lemma": "scientist"},
        },
        metadata={
            "wrapper_construction_id": "topic_comment_copular",
            "base_construction_id": "copula_equative_classification",
        },
        lexical_bindings={"comment": {"lemma": "scientist", "pos": "N"}},
    )

    plain = ConstructionPlan(
        construction_id="copula_equative_classification",
        lang_code="eng",
        slot_map={"subject": {"id": "Q1"}},
    )

    assert wrapped.is_wrapper_plan is True
    assert wrapped.wrapper_construction_id == "topic_comment_copular"
    assert wrapped.base_construction_id == "copula_equative_classification"

    assert plain.is_wrapper_plan is False
    assert plain.wrapper_construction_id is None
    assert plain.base_construction_id == "copula_equative_classification"

    assert wrapped.required_slots_present(["topic", "comment"]) is True
    assert wrapped.required_slots_present(["topic", "comment", "copula"]) is False

    assert wrapped.summary() == {
        "construction_id": "topic_comment_copular",
        "lang_code": "eng",
        "slot_keys": ["topic", "comment"],
        "topic_entity_id": None,
        "focus_role": None,
        "has_lexical_bindings": True,
        "is_wrapper_plan": True,
        "base_construction_id": "copula_equative_classification",
    }


def test_validate_returns_self_for_explicit_contract_checks():
    plan = ConstructionPlan(
        construction_id="copula_equative_classification",
        lang_code="eng",
        slot_map={"subject": {"id": "Q1"}, "predicate_nominal": "scientist"},
        generation_options={"register": "formal"},
    )

    assert plan.validate() is plan