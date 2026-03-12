# tests/integration/test_generate_via_planner_en.py
from __future__ import annotations

from typing import Any

import pytest

from app.core.domain.exceptions import DomainError
from app.core.domain.models import Frame, SurfaceResult
from app.core.domain.planning.construction_plan import ConstructionPlan
from app.core.domain.planning.planned_sentence import PlannedSentence
from app.core.use_cases.generate_text import GenerateText


def _english_bio_frame() -> Frame:
    return Frame(
        frame_type="bio",
        subject={
            "name": "Alan Turing",
            "qid": "Q7251",
        },
        properties={
            "profession": "mathematician",
            "nationality": "British",
        },
        meta={
            "source_id": "integration_en_bio_001",
        },
    )


class RecordingPlanner:
    def __init__(self, construction_id: str = "copula_equative_classification") -> None:
        self.construction_id = construction_id
        self.calls: list[dict[str, Any]] = []

    async def plan(self, frames: Any, *, lang_code: str, domain: str | None = None) -> list[PlannedSentence]:
        frame = frames[0] if isinstance(frames, (list, tuple)) else frames
        self.calls.append(
            {
                "lang_code": lang_code,
                "domain": domain,
                "frame_type": getattr(frame, "frame_type", None),
                "subject_name": getattr(frame, "subject", {}).get("name"),
            }
        )

        return [
            PlannedSentence(
                construction_id=self.construction_id,
                lang_code=lang_code,
                frame=frame,
                topic_entity_id="Q7251",
                focus_role="predicate_nominal",
                discourse_mode="declarative",
                generation_options={"register": "default"},
                metadata={"planner_stage": "integration_test"},
                source_frame_ids=("integration_en_bio_001",),
                priority=1,
            )
        ]


class RecordingLexicalResolver:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def resolve(
        self,
        payload: PlannedSentence,
        *,
        lang_code: str | None = None,
        frame: Frame | None = None,
    ) -> ConstructionPlan:
        assert isinstance(payload, PlannedSentence)

        resolved_lang = lang_code or payload.lang_code
        frame_subject = getattr(frame, "subject", {}) if frame is not None else {}
        frame_props = getattr(frame, "properties", {}) if frame is not None else {}

        plan = ConstructionPlan(
            construction_id=payload.construction_id,
            lang_code=resolved_lang,
            slot_map={
                "subject": {
                    "qid": frame_subject.get("qid", "Q7251"),
                    "name": frame_subject.get("name", "Alan Turing"),
                    "entity_type": "person",
                },
                "predicate_nominal": {
                    "lemma": frame_props.get("profession", "mathematician"),
                    "surface": frame_props.get("profession", "mathematician"),
                    "pos": "noun",
                },
                "nationality": {
                    "lemma": frame_props.get("nationality", "British"),
                    "surface": frame_props.get("nationality", "British"),
                    "pos": "adj",
                },
            },
            generation_options=dict(payload.generation_options),
            topic_entity_id=payload.topic_entity_id,
            focus_role=payload.focus_role,
            lexical_bindings={
                "predicate_nominal": {
                    "lemma": frame_props.get("profession", "mathematician"),
                    "source": "test_lexicon",
                    "confidence": 1.0,
                },
                "nationality": {
                    "lemma": frame_props.get("nationality", "British"),
                    "source": "test_lexicon",
                    "confidence": 1.0,
                },
            },
            provenance={
                "source_frame_ids": list(payload.source_frame_ids or ()),
                "resolver": "integration_test",
            },
            metadata={
                "planner_stage": "integration_test",
                "source_frame_id": payload.primary_source_frame_id,
            },
        )

        self.calls.append(
            {
                "planned_sentence": payload,
                "construction_plan": plan,
            }
        )
        return plan


class RecordingFamilyRealizer:
    backend_name = "family"

    def __init__(self) -> None:
        self.calls: list[ConstructionPlan] = []

    async def realize(
        self,
        payload: ConstructionPlan,
        *,
        lang_code: str | None = None,
        frame: Frame | None = None,
    ) -> SurfaceResult:
        assert isinstance(payload, ConstructionPlan)
        self.calls.append(payload)

        subject = payload.get_slot("subject")
        profession_binding = payload.lexical_bindings["predicate_nominal"]
        profession = profession_binding.get("lemma", "mathematician")

        text = f"{subject['name']} is a {profession}."

        return SurfaceResult(
            text=text,
            lang_code=lang_code or payload.lang_code,
            construction_id=payload.construction_id,
            renderer_backend=self.backend_name,
            fallback_used=False,
            tokens=text.rstrip(".").split(),
            debug_info={
                "selected_backend": self.backend_name,
                "slot_keys": list(payload.slot_keys()),
                "lexical_binding_keys": sorted(payload.lexical_bindings.keys()),
            },
        )


class FailingRealizer:
    backend_name = "family"

    def __init__(self) -> None:
        self.calls: list[ConstructionPlan] = []

    async def realize(
        self,
        payload: ConstructionPlan,
        *,
        lang_code: str | None = None,
        frame: Frame | None = None,
    ) -> SurfaceResult:
        assert isinstance(payload, ConstructionPlan)
        self.calls.append(payload)
        raise RuntimeError("realizer exploded")


@pytest.mark.asyncio
async def test_generate_text_english_uses_planner_first_runtime_end_to_end() -> None:
    frame = _english_bio_frame()
    planner = RecordingPlanner()
    resolver = RecordingLexicalResolver()
    realizer = RecordingFamilyRealizer()

    use_case = GenerateText(
        planner=planner,
        lexical_resolver=resolver,
        realizer=realizer,
        engine=None,
        allow_legacy_engine_fallback=False,
    )

    result = await use_case.execute("eng", frame)

    assert result.text == "Alan Turing is a mathematician."
    assert result.lang_code == "eng"

    assert result.debug_info["runtime_path"] == "planner_first"
    assert result.debug_info["fallback_used"] is False
    assert result.debug_info["construction_id"] == "copula_equative_classification"
    assert result.debug_info["renderer_backend"] == "family"
    assert result.debug_info["selected_backend"] == "family"
    assert result.debug_info["lexical_resolver"] == "RecordingLexicalResolver"
    assert result.debug_info["planner"] == "RecordingPlanner"
    assert result.debug_info["realizer"] == "RecordingFamilyRealizer"
    assert result.debug_info["slot_keys"] == ["subject", "predicate_nominal", "nationality"]
    assert result.debug_info["lexical_binding_keys"] == ["nationality", "predicate_nominal"]

    assert len(planner.calls) == 1
    assert planner.calls[0]["lang_code"] == "eng"
    assert planner.calls[0]["frame_type"] == "bio"

    assert len(resolver.calls) == 1
    planned_sentence = resolver.calls[0]["planned_sentence"]
    construction_plan = resolver.calls[0]["construction_plan"]

    assert isinstance(planned_sentence, PlannedSentence)
    assert planned_sentence.construction_id == "copula_equative_classification"
    assert planned_sentence.lang_code == "eng"

    assert isinstance(construction_plan, ConstructionPlan)
    assert construction_plan.construction_id == "copula_equative_classification"
    assert construction_plan.lang_code == "eng"
    assert construction_plan.get_slot("subject")["name"] == "Alan Turing"
    assert construction_plan.get_slot("predicate_nominal")["lemma"] == "mathematician"

    assert len(realizer.calls) == 1
    realized_plan = realizer.calls[0]
    assert realized_plan.construction_id == "copula_equative_classification"
    assert realized_plan.lang_code == "eng"
    assert realized_plan.lexical_bindings["predicate_nominal"]["lemma"] == "mathematician"


@pytest.mark.asyncio
async def test_generate_text_english_is_deterministic_and_does_not_mutate_plan_slots() -> None:
    frame = _english_bio_frame()
    planner = RecordingPlanner()
    resolver = RecordingLexicalResolver()
    realizer = RecordingFamilyRealizer()

    use_case = GenerateText(
        planner=planner,
        lexical_resolver=resolver,
        realizer=realizer,
        engine=None,
        allow_legacy_engine_fallback=False,
    )

    first = await use_case.execute("eng", frame)
    second = await use_case.execute("eng", frame)

    assert first.text == second.text == "Alan Turing is a mathematician."
    assert first.debug_info["construction_id"] == second.debug_info["construction_id"]
    assert first.debug_info["renderer_backend"] == second.debug_info["renderer_backend"]
    assert first.debug_info["runtime_path"] == second.debug_info["runtime_path"] == "planner_first"

    assert len(realizer.calls) == 2
    first_plan = realizer.calls[0]
    second_plan = realizer.calls[1]

    assert first_plan is not second_plan
    assert first_plan.to_dict() == second_plan.to_dict()

    assert first_plan.slot_keys() == ("subject", "predicate_nominal", "nationality")
    with pytest.raises(TypeError):
        first_plan.slot_map["subject"] = {"name": "Changed"}

    assert first_plan.lexical_bindings["predicate_nominal"]["lemma"] == "mathematician"
    assert second_plan.lexical_bindings["predicate_nominal"]["lemma"] == "mathematician"


@pytest.mark.asyncio
async def test_generate_text_english_realizer_failure_is_explicit_without_hidden_success() -> None:
    frame = _english_bio_frame()
    planner = RecordingPlanner()
    resolver = RecordingLexicalResolver()
    realizer = FailingRealizer()

    use_case = GenerateText(
        planner=planner,
        lexical_resolver=resolver,
        realizer=realizer,
        engine=None,
        allow_legacy_engine_fallback=False,
    )

    with pytest.raises(DomainError) as excinfo:
        await use_case.execute("eng", frame)

    assert "Unexpected generation failure" in str(excinfo.value)
    assert "realizer exploded" in str(excinfo.value)

    assert len(planner.calls) == 1
    assert len(resolver.calls) == 1
    assert len(realizer.calls) == 1