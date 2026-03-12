from __future__ import annotations

from collections.abc import Iterable

import pytest

from app.core.domain.exceptions import DomainError, InvalidFrameError
from app.core.domain.models import Frame
from app.core.domain.planning.planned_sentence import PlannedSentence
from app.core.use_cases.plan_text import PlanText
import app.core.use_cases.plan_text as plan_text_module


def _bio_frame(name: str = "Alan Turing") -> Frame:
    return Frame(
        frame_type="bio",
        subject={"name": name, "qid": "Q7251"},
        properties={"profession": "mathematician"},
        meta={"source": "unit-test"},
    )


@pytest.fixture(autouse=True)
def _reset_lexicon(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Keep language normalization deterministic in unit tests unless a test
    intentionally overrides it.
    """
    monkeypatch.setattr(plan_text_module, "lexicon", None)


class RecordingKeywordPlanner:
    def __init__(self, result):
        self.result = result
        self.calls: list[tuple[str, object]] = []

    async def plan(self, *, lang_code: str, frame: object):
        self.calls.append((lang_code, frame))
        return self.result


class RecordingPlanTextPlanner:
    def __init__(self, result):
        self.result = result
        self.calls: list[tuple[str, object]] = []

    async def plan_text(self, *, lang_code: str, frame: object):
        self.calls.append((lang_code, frame))
        return self.result


class RecordingPositionalExecutePlanner:
    def __init__(self, result):
        self.result = result
        self.calls: list[tuple[str, object]] = []

    async def execute(self, lang_code: str, frame: object):
        self.calls.append((lang_code, frame))
        return self.result


class GeneratorPlanner:
    def __init__(self, items: Iterable[object]):
        self.items = list(items)
        self.calls: list[tuple[str, object]] = []

    async def plan(self, *, lang_code: str, frame: object):
        self.calls.append((lang_code, frame))
        return (item for item in self.items)


class StringPlanner:
    async def plan(self, *, lang_code: str, frame: object):
        return "not-a-valid-plan"


class NoEntrypointPlanner:
    pass


class DumpablePlan:
    def __init__(self, payload: dict):
        self._payload = payload

    def model_dump(self) -> dict:
        return dict(self._payload)


@pytest.mark.asyncio
async def test_execute_returns_planned_sentences_from_canonical_planner() -> None:
    frame = _bio_frame()
    planner_result = PlannedSentence.for_frame(
        frame=frame,
        construction_id="copula_equative_simple",
        lang_code="en",
        topic_entity_id="Q7251",
        focus_role="profession",
        metadata={"planner": "unit"},
    )
    planner = RecordingKeywordPlanner(planner_result)
    use_case = PlanText(planner=planner)

    result = await use_case.execute("EN", frame)

    assert isinstance(result, list)
    assert len(result) == 1
    assert isinstance(result[0], PlannedSentence)
    assert result[0].construction_id == "copula_equative_simple"
    assert result[0].lang_code == "en"
    assert result[0].topic_entity_id == "Q7251"
    assert result[0].focus_role == "profession"
    assert dict(result[0].metadata) == {"planner": "unit"}
    assert planner.calls == [("en", frame)]


@pytest.mark.asyncio
async def test_execute_uses_lexicon_normalize_code_when_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame = _bio_frame()
    planner_result = PlannedSentence.for_frame(
        frame=frame,
        construction_id="copula_equative_simple",
        lang_code="fra",
    )
    planner = RecordingKeywordPlanner(planner_result)
    use_case = PlanText(planner=planner)

    class DummyLexicon:
        @staticmethod
        def normalize_code(value: str) -> str:
            assert value == "fr-ca"
            return "fra"

    monkeypatch.setattr(plan_text_module, "lexicon", DummyLexicon())

    result = await use_case.execute("FR-CA", frame)

    assert len(result) == 1
    assert planner.calls == [("fra", frame)]


@pytest.mark.asyncio
async def test_execute_falls_back_to_legacy_plan_text_entrypoint() -> None:
    frame = _bio_frame()
    planner_payload = {
        "construction_id": "copula_equative_simple",
        "lang_code": "en",
        "frame": frame,
        "topic_entity_id": "Q7251",
        "focus_role": "profession",
        "metadata": {"planner_method": "plan_text"},
    }
    planner = RecordingPlanTextPlanner(planner_payload)
    use_case = PlanText(planner=planner)

    result = await use_case.execute("eng", frame)

    assert len(result) == 1
    assert result[0].construction_id == "copula_equative_simple"
    assert result[0].lang_code == "en"
    assert result[0].topic_entity_id == "Q7251"
    assert result[0].focus_role == "profession"
    assert dict(result[0].metadata) == {"planner_method": "plan_text"}
    assert planner.calls == [("en", frame)]


@pytest.mark.asyncio
async def test_execute_falls_back_to_legacy_execute_entrypoint_with_positional_signature() -> None:
    frame = _bio_frame()
    planner_payload = {
        "construction_id": "copula_equative_simple",
        "lang_code": "en",
        "frame": frame,
        "metadata": {"planner_method": "execute"},
    }
    planner = RecordingPositionalExecutePlanner(planner_payload)
    use_case = PlanText(planner=planner)

    result = await use_case.execute("ENG", frame)

    assert len(result) == 1
    assert result[0].construction_id == "copula_equative_simple"
    assert dict(result[0].metadata) == {"planner_method": "execute"}
    assert planner.calls == [("en", frame)]


@pytest.mark.asyncio
async def test_execute_accepts_iterable_of_mapping_like_plans() -> None:
    frame = _bio_frame()
    planner = GeneratorPlanner(
        [
            {
                "construction_id": "copula_equative_simple",
                "lang_code": "en",
                "frame": frame,
                "focus_role": "profession",
            },
            {
                "construction_id": "topic_comment_copular",
                "lang_code": "en",
                "frame": frame,
                "focus_role": "topic",
            },
        ]
    )
    use_case = PlanText(planner=planner)

    result = await use_case.execute("en", frame)

    assert [item.construction_id for item in result] == [
        "copula_equative_simple",
        "topic_comment_copular",
    ]
    assert [item.focus_role for item in result] == ["profession", "topic"]
    assert planner.calls == [("en", frame)]


@pytest.mark.asyncio
async def test_execute_accepts_model_dump_style_planner_items() -> None:
    frame = _bio_frame()
    planner = RecordingKeywordPlanner(
        DumpablePlan(
            {
                "construction_id": "copula_equative_simple",
                "lang_code": "en",
                "frame": frame,
                "topic_entity_id": "Q7251",
                "metadata": {"shape": "model_dump"},
            }
        )
    )
    use_case = PlanText(planner=planner)

    result = await use_case.execute("en", frame)

    assert len(result) == 1
    assert result[0].construction_id == "copula_equative_simple"
    assert result[0].topic_entity_id == "Q7251"
    assert dict(result[0].metadata) == {"shape": "model_dump"}


@pytest.mark.asyncio
async def test_execute_one_returns_single_plan() -> None:
    frame = _bio_frame()
    planner = RecordingKeywordPlanner(
        PlannedSentence.for_frame(
            frame=frame,
            construction_id="copula_equative_simple",
            lang_code="en",
        )
    )
    use_case = PlanText(planner=planner)

    result = await use_case.execute_one("en", frame)

    assert isinstance(result, PlannedSentence)
    assert result.construction_id == "copula_equative_simple"


@pytest.mark.asyncio
async def test_execute_one_raises_when_multiple_plans_are_returned() -> None:
    frame = _bio_frame()
    planner = RecordingKeywordPlanner(
        [
            PlannedSentence.for_frame(
                frame=frame,
                construction_id="copula_equative_simple",
                lang_code="en",
            ),
            PlannedSentence.for_frame(
                frame=frame,
                construction_id="topic_comment_copular",
                lang_code="en",
            ),
        ]
    )
    use_case = PlanText(planner=planner)

    with pytest.raises(DomainError, match="Expected exactly one planned sentence"):
        await use_case.execute_one("en", frame)


@pytest.mark.asyncio
async def test_execute_rejects_invalid_bio_frame_before_planner_call() -> None:
    invalid_frame = {
        "frame_type": "bio",
        "subject": {},
        "properties": {"profession": "mathematician"},
    }
    planner = RecordingKeywordPlanner([])
    use_case = PlanText(planner=planner)

    with pytest.raises(InvalidFrameError, match="subject with a non-empty 'name'"):
        await use_case.execute("en", invalid_frame)

    assert planner.calls == []


@pytest.mark.asyncio
async def test_execute_raises_when_planner_has_no_supported_entrypoint() -> None:
    frame = _bio_frame()
    use_case = PlanText(planner=NoEntrypointPlanner())

    with pytest.raises(DomainError, match="supported planning entrypoint"):
        await use_case.execute("en", frame)


@pytest.mark.asyncio
async def test_execute_raises_when_planner_returns_invalid_string_like_result() -> None:
    frame = _bio_frame()
    use_case = PlanText(planner=StringPlanner())

    with pytest.raises(DomainError, match="invalid string-like result"):
        await use_case.execute("en", frame)


@pytest.mark.asyncio
async def test_execute_raises_when_planner_returns_empty_sequence() -> None:
    frame = _bio_frame()
    planner = RecordingKeywordPlanner([])
    use_case = PlanText(planner=planner)

    with pytest.raises(DomainError, match="produced no sentence plans"):
        await use_case.execute("en", frame)


@pytest.mark.asyncio
async def test_execute_raises_when_planner_returns_non_canonical_construction_id() -> None:
    frame = _bio_frame()
    planner = RecordingKeywordPlanner(
        {
            "construction_id": "relation.temporal",
            "lang_code": "en",
            "frame": frame,
        }
    )
    use_case = PlanText(planner=planner)

    with pytest.raises(DomainError, match="Unexpected planning failure"):
        await use_case.execute("en", frame)


@pytest.mark.asyncio
async def test_execute_raises_when_planner_output_omits_frame() -> None:
    frame = _bio_frame()
    planner = RecordingKeywordPlanner(
        {
            "construction_id": "copula_equative_simple",
            "lang_code": "en",
            "topic_entity_id": "Q7251",
        }
    )
    use_case = PlanText(planner=planner)

    with pytest.raises(DomainError, match="without a frame"):
        await use_case.execute("en", frame)