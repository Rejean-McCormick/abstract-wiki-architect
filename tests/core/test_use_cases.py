from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.domain.events import EventType
from app.core.domain.exceptions import DomainError, InvalidFrameError
from app.core.domain.models import Frame, Sentence
from app.core.use_cases.build_language import BuildLanguage
from app.core.use_cases.generate_text import GenerateText


def _sample_frame() -> Frame:
    return Frame(
        frame_type="bio",
        subject={
            "name": "Alan Turing",
            "qid": "Q7251",
            "gender": "male",
        },
        properties={
            "profession": "mathematician",
            "nationality": "British",
        },
        meta={"tone": "formal"},
    )


@pytest.mark.asyncio
class TestGenerateText:
    async def test_execute_uses_planner_first_runtime_and_preserves_runtime_metadata(self):
        frame = _sample_frame()

        planner = MagicMock()
        planner.plan = AsyncMock(
            return_value={
                "construction_id": "copula_equative_classification",
                "lang_code": "eng",
                "slot_map": {"subject": "Alan Turing"},
            }
        )

        lexical_resolver = MagicMock()
        lexical_resolver.resolve = AsyncMock(
            return_value={
                "construction_id": "copula_equative_classification",
                "lang_code": "eng",
                "slot_map": {"subject": "Alan Turing"},
                "lexical_bindings": {
                    "profession": {"lemma": "mathematician"},
                    "nationality": {"lemma": "British"},
                },
            }
        )

        realizer = MagicMock()
        realizer.realize = AsyncMock(
            return_value=SimpleNamespace(
                text="Alan Turing is a British mathematician.",
                lang_code="eng",
                construction_id="copula_equative_classification",
                renderer_backend="family",
                fallback_used=False,
                tokens=["Alan", "Turing", "is", "a", "British", "mathematician."],
                selected_backend="family",
                debug_info={
                    "selected_backend": "family",
                    "construction_id": "copula_equative_classification",
                    "renderer_backend": "family",
                },
                generation_time_ms=12.5,
            )
        )

        legacy_engine = MagicMock()
        legacy_engine.generate = AsyncMock()

        use_case = GenerateText(
            engine=legacy_engine,
            planner=planner,
            lexical_resolver=lexical_resolver,
            realizer=realizer,
        )

        result = await use_case.execute("eng", frame)

        assert isinstance(result, Sentence)
        assert result.text == "Alan Turing is a British mathematician."
        assert result.lang_code == "eng"
        assert result.generation_time_ms == 12.5

        assert result.debug_info["runtime_path"] == "planner_first"
        assert result.debug_info["fallback_used"] is False
        assert result.debug_info["construction_id"] == "copula_equative_classification"
        assert result.debug_info["renderer_backend"] == "family"
        assert result.debug_info["selected_backend"] == "family"
        assert result.debug_info["planner"] == planner.__class__.__name__
        assert result.debug_info["lexical_resolver"] == lexical_resolver.__class__.__name__
        assert result.debug_info["realizer"] == realizer.__class__.__name__

        planner.plan.assert_awaited_once()
        lexical_resolver.resolve.assert_awaited_once()
        realizer.realize.assert_awaited_once()
        legacy_engine.generate.assert_not_called()

    async def test_execute_falls_back_to_legacy_engine_when_planner_runtime_fails(self):
        frame = _sample_frame()

        planner = MagicMock()
        planner.plan = AsyncMock(side_effect=RuntimeError("planner exploded"))

        lexical_resolver = MagicMock()
        lexical_resolver.resolve = AsyncMock()

        realizer = MagicMock()
        realizer.realize = AsyncMock()

        legacy_engine = MagicMock()
        legacy_engine.generate = AsyncMock(
            return_value=Sentence(
                text="Alan Turing is a Mathematician.",
                lang_code="eng",
            )
        )

        use_case = GenerateText(
            engine=legacy_engine,
            planner=planner,
            lexical_resolver=lexical_resolver,
            realizer=realizer,
            allow_legacy_engine_fallback=True,
        )

        result = await use_case.execute("eng", frame)

        assert result.text == "Alan Turing is a Mathematician."
        assert result.lang_code == "eng"
        assert result.debug_info["runtime_path"] == "legacy_engine_fallback"
        assert result.debug_info["fallback_used"] is True
        assert "planner exploded" in result.debug_info["fallback_reason"]
        assert result.debug_info["planner_runtime_configured"] is True
        assert result.debug_info["legacy_engine"] == legacy_engine.__class__.__name__

        planner.plan.assert_awaited_once()
        legacy_engine.generate.assert_awaited_once_with("eng", frame)
        lexical_resolver.resolve.assert_not_called()
        realizer.realize.assert_not_called()

    async def test_execute_does_not_silently_fallback_when_fallback_is_disabled(self):
        frame = _sample_frame()

        planner = MagicMock()
        planner.plan = AsyncMock(side_effect=RuntimeError("planner exploded"))

        realizer = MagicMock()
        realizer.realize = AsyncMock()

        legacy_engine = MagicMock()
        legacy_engine.generate = AsyncMock()

        use_case = GenerateText(
            engine=legacy_engine,
            planner=planner,
            realizer=realizer,
            allow_legacy_engine_fallback=False,
        )

        with pytest.raises(DomainError) as excinfo:
            await use_case.execute("eng", frame)

        assert "Unexpected generation failure: planner exploded" in str(excinfo.value)
        planner.plan.assert_awaited_once()
        legacy_engine.generate.assert_not_called()

    async def test_execute_uses_legacy_engine_when_planner_runtime_is_not_configured(self):
        frame = _sample_frame()

        legacy_engine = MagicMock()
        legacy_engine.generate = AsyncMock(
            return_value=Sentence(
                text="Alan Turing is a Mathematician.",
                lang_code="eng",
                debug_info={"legacy_note": "compatibility"},
            )
        )

        use_case = GenerateText(engine=legacy_engine)

        result = await use_case.execute("eng", frame)

        assert result.text == "Alan Turing is a Mathematician."
        assert result.lang_code == "eng"
        assert result.debug_info["runtime_path"] == "legacy_engine"
        assert result.debug_info["fallback_used"] is False
        assert result.debug_info["legacy_note"] == "compatibility"

        legacy_engine.generate.assert_awaited_once_with("eng", frame)

    async def test_execute_rejects_invalid_frame_immediately(self):
        use_case = GenerateText(engine=MagicMock(generate=AsyncMock()))

        invalid_frame = SimpleNamespace(frame_type="", subject={})

        with pytest.raises(InvalidFrameError, match="frame_type"):
            await use_case.execute("eng", invalid_frame)

    async def test_execute_rejects_bio_frame_without_subject_name(self):
        use_case = GenerateText(engine=MagicMock(generate=AsyncMock()))

        invalid_frame = Frame(
            frame_type="bio",
            subject={},
            properties={"profession": "mathematician"},
        )

        with pytest.raises(InvalidFrameError, match="subject"):
            await use_case.execute("eng", invalid_frame)

    async def test_execute_rejects_empty_lang_code(self):
        use_case = GenerateText(engine=MagicMock(generate=AsyncMock()))

        with pytest.raises(DomainError, match="lang_code must be a non-empty string"):
            await use_case.execute("", _sample_frame())

    async def test_execute_fails_cleanly_when_no_runtime_and_no_legacy_engine_are_configured(
        self,
    ):
        use_case = GenerateText()

        with pytest.raises(DomainError) as excinfo:
            await use_case.execute("eng", _sample_frame())

        assert (
            "GenerateText is not configured with either a planner-first runtime "
            "or a legacy grammar engine." in str(excinfo.value)
        )

    async def test_execute_wraps_unmappable_realizer_output_in_domain_error(self):
        frame = _sample_frame()

        planner = MagicMock()
        planner.plan = AsyncMock(
            return_value={
                "construction_id": "copula_equative_classification",
                "lang_code": "eng",
                "slot_map": {"subject": "Alan Turing"},
            }
        )

        realizer = MagicMock()
        realizer.realize = AsyncMock(return_value=object())

        use_case = GenerateText(
            planner=planner,
            realizer=realizer,
            allow_legacy_engine_fallback=False,
        )

        with pytest.raises(DomainError) as excinfo:
            await use_case.execute("eng", frame)

        assert "Unexpected generation failure" in str(excinfo.value)
        assert "missing 'text'" in str(excinfo.value)

    async def test_execute_planner_first_result_is_deterministic_across_repeated_calls(self):
        frame = _sample_frame()

        planner = MagicMock()
        planner.plan = AsyncMock(
            return_value={
                "construction_id": "copula_equative_classification",
                "lang_code": "eng",
                "slot_map": {"subject": "Alan Turing"},
            }
        )

        realizer = MagicMock()
        realizer.realize = AsyncMock(
            return_value=SimpleNamespace(
                text="Alan Turing is a British mathematician.",
                lang_code="eng",
                construction_id="copula_equative_classification",
                renderer_backend="family",
                fallback_used=False,
                tokens=["Alan", "Turing", "is", "a", "British", "mathematician."],
                debug_info={"selected_backend": "family"},
                generation_time_ms=5.0,
            )
        )

        use_case = GenerateText(planner=planner, realizer=realizer)

        first = await use_case.execute("eng", frame)
        second = await use_case.execute("eng", frame)

        assert first.text == second.text
        assert first.lang_code == second.lang_code
        assert first.debug_info["runtime_path"] == "planner_first"
        assert second.debug_info["runtime_path"] == "planner_first"


@pytest.mark.asyncio
class TestBuildLanguage:
    async def test_execute_success(self):
        mock_broker = MagicMock()
        mock_broker.publish = AsyncMock()

        mock_task_queue = MagicMock()
        mock_task_queue.enqueue_language_build = AsyncMock(return_value="job_build_123")

        use_case = BuildLanguage(task_queue=mock_task_queue, broker=mock_broker)

        event_id = await use_case.execute("deu", "fast")

        assert event_id is not None
        assert isinstance(event_id, str)

        mock_broker.publish.assert_awaited_once()
        published_event = mock_broker.publish.call_args[0][0]
        assert published_event.type == EventType.BUILD_REQUESTED
        assert published_event.payload["lang_code"] == "deu"
        assert published_event.payload["strategy"] == "fast"

        mock_task_queue.enqueue_language_build.assert_awaited_once()
        kwargs = mock_task_queue.enqueue_language_build.call_args.kwargs
        assert kwargs["lang_code"] == "deu"
        assert kwargs["strategy"] == "fast"
        assert kwargs["correlation_id"] == event_id
        assert isinstance(kwargs.get("trace_context"), dict)

    async def test_execute_invalid_strategy(self):
        mock_broker = MagicMock()
        mock_broker.publish = AsyncMock()

        mock_task_queue = MagicMock()
        mock_task_queue.enqueue_language_build = AsyncMock()

        use_case = BuildLanguage(task_queue=mock_task_queue, broker=mock_broker)

        with pytest.raises(DomainError) as excinfo:
            await use_case.execute("deu", strategy="magic_wand")

        assert "Invalid build strategy" in str(excinfo.value)
        mock_broker.publish.assert_not_called()
        mock_task_queue.enqueue_language_build.assert_not_called()

    async def test_execute_wraps_queue_failure_in_domain_error(self):
        mock_broker = MagicMock()
        mock_broker.publish = AsyncMock()

        mock_task_queue = MagicMock()
        mock_task_queue.enqueue_language_build = AsyncMock(
            side_effect=RuntimeError("redis unavailable")
        )

        use_case = BuildLanguage(task_queue=mock_task_queue, broker=mock_broker)

        with pytest.raises(DomainError) as excinfo:
            await use_case.execute("deu", strategy="fast")

        assert "Failed to queue build request" in str(excinfo.value)
        assert "redis unavailable" in str(excinfo.value)
        mock_broker.publish.assert_awaited_once()
        mock_task_queue.enqueue_language_build.assert_awaited_once()