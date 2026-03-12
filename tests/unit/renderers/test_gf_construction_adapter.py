# tests/unit/renderers/test_gf_construction_adapter.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from app.adapters.engines.gf_construction_adapter import (
    GFConstructionAdapter,
    RealizationError,
)
from app.core.domain.planning.construction_plan import ConstructionPlan


@dataclass
class FakeGFEngine:
    status_payload: dict[str, Any] = field(default_factory=lambda: {"loaded": True})
    linearize_value: str = "Marie Curie is a physicist."
    resolved_languages: dict[str, str] = field(
        default_factory=lambda: {
            "eng": "WikiEng",
            "en": "WikiEng",
            "fra": "WikiFre",
            "fr": "WikiFre",
        }
    )

    linearize_calls: list[tuple[str, str]] = field(default_factory=list)

    async def status(self) -> dict[str, Any]:
        return dict(self.status_payload)

    def linearize(self, expr: Any, language: str) -> str:
        self.linearize_calls.append((str(expr), language))
        return self.linearize_value

    def _resolve_concrete_name(self, lang_code: str) -> str | None:
        return self.resolved_languages.get(lang_code)


def _plan(
    *,
    construction_id: str = "copula_equative_simple",
    lang_code: str = "eng",
    slot_map: dict[str, Any] | None = None,
    lexical_bindings: dict[str, Any] | None = None,
    generation_options: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> ConstructionPlan:
    return ConstructionPlan(
        construction_id=construction_id,
        lang_code=lang_code,
        slot_map=slot_map or {"subject": "Marie Curie", "profession": "physicist"},
        lexical_bindings=lexical_bindings or {},
        generation_options=generation_options or {},
        metadata=metadata or {},
    )


def test_supports_and_support_status_cover_direct_and_wrapper_paths() -> None:
    adapter = GFConstructionAdapter(engine=FakeGFEngine())

    assert adapter.supports("copula-equative-simple", "eng") is True
    assert adapter.get_support_status("copula-equative-simple", "eng") == "full"

    assert adapter.supports("topic comment copular", "eng") is True
    assert adapter.get_support_status("topic comment copular", "eng") == "partial"

    assert adapter.supports("intransitive_event", "eng") is False
    assert adapter.get_support_status("intransitive_event", "eng") == "unsupported"


@pytest.mark.asyncio
async def test_realize_direct_plan_returns_surface_result_and_debug_info() -> None:
    engine = FakeGFEngine(linearize_value="Marie Curie is a Polish physicist.")
    adapter = GFConstructionAdapter(engine=engine)

    plan = _plan(
        construction_id="copula_equative_classification",
        slot_map={
            "subject": "Marie Curie",
            "predicate_nominal": {
                "head": "physicist",
                "modifier": "Polish",
            },
        },
    )

    result = await adapter.realize(plan)

    expected_ast = (
        'mkBioFull (mkEntityStr "Marie Curie") '
        '(strProf "physicist") (strNat "Polish")'
    )

    assert engine.linearize_calls == [(expected_ast, "eng")]
    assert result.text == "Marie Curie is a Polish physicist."
    assert result.lang_code == "eng"
    assert result.construction_id == "copula_equative_classification"
    assert result.renderer_backend == "gf"
    assert result.fallback_used is False
    assert result.tokens == ["Marie", "Curie", "is", "a", "Polish", "physicist."]

    assert result.debug_info["renderer_backend"] == "gf"
    assert result.debug_info["construction_id"] == "copula_equative_classification"
    assert result.debug_info["resolved_language"] == "WikiEng"
    assert result.debug_info["selected_backend"] == "gf"
    assert result.debug_info["attempted_backends"] == ["gf"]
    assert result.debug_info["capability_tier"] == "full"
    assert result.debug_info["effective_construction_id"] == "copula_equative_classification"
    assert result.debug_info["ast"] == expected_ast
    assert "validated_construction_plan" in result.debug_info["backend_trace"]
    assert "mapped_slot_map_to_gf_arguments" in result.debug_info["backend_trace"]
    assert "selected_mkBioFull" in result.debug_info["backend_trace"]
    assert "linearized_ast" in result.debug_info["backend_trace"]


@pytest.mark.asyncio
async def test_realize_wrapper_passthrough_records_fallback_and_wrapper_metadata() -> None:
    engine = FakeGFEngine(linearize_value="Marie Curie is a physicist.")
    adapter = GFConstructionAdapter(engine=engine, allow_wrapper_passthrough=True)

    plan = _plan(
        construction_id="topic_comment_copular",
        slot_map={"subject": "Marie Curie"},
        lexical_bindings={"profession": "physicist"},
        metadata={
            "wrapper_construction_id": "topic_comment_copular",
            "base_construction_id": "copula_equative_simple",
        },
    )

    result = await adapter.realize(plan)

    expected_ast = 'mkBioProf (mkEntityStr "Marie Curie") (strProf "physicist")'

    assert engine.linearize_calls == [(expected_ast, "eng")]
    assert result.fallback_used is True
    assert result.renderer_backend == "gf"
    assert result.debug_info["effective_construction_id"] == "copula_equative_simple"
    assert result.debug_info["capability_tier"] == "partial"
    assert result.debug_info["wrapper_construction_id"] == "topic_comment_copular"
    assert result.debug_info["base_construction_id"] == "copula_equative_simple"
    assert result.debug_info["lexical_binding_keys"] == ["profession"]
    assert "wrapper_passthrough_to_base_construction" in result.debug_info["backend_trace"]


@pytest.mark.asyncio
async def test_realize_defaults_missing_predicate_nominal_when_fallback_allowed() -> None:
    engine = FakeGFEngine(linearize_value="Marie Curie is a person.")
    adapter = GFConstructionAdapter(engine=engine)

    plan = _plan(
        slot_map={"subject": "Marie Curie"},
        generation_options={"allow_fallback": True},
    )

    result = await adapter.realize(plan)

    expected_ast = 'mkBioProf (mkEntityStr "Marie Curie") (strProf "person")'

    assert engine.linearize_calls == [(expected_ast, "eng")]
    assert result.fallback_used is True
    assert result.debug_info["ast"] == expected_ast
    assert "defaulted_missing_predicate_nominal_to_person" in result.debug_info["backend_trace"]


@pytest.mark.asyncio
async def test_realize_rejects_missing_predicate_when_fallback_disabled() -> None:
    adapter = GFConstructionAdapter(engine=FakeGFEngine())

    plan = _plan(
        slot_map={"subject": "Marie Curie"},
        generation_options={"allow_fallback": False},
    )

    with pytest.raises(RealizationError, match="allow_fallback is disabled"):
        await adapter.realize(plan)


@pytest.mark.asyncio
async def test_realize_rejects_missing_subject() -> None:
    adapter = GFConstructionAdapter(engine=FakeGFEngine())

    plan = _plan(slot_map={"profession": "physicist"})

    with pytest.raises(RealizationError, match="requires a subject"):
        await adapter.realize(plan)


@pytest.mark.asyncio
async def test_realize_rejects_unloaded_runtime() -> None:
    engine = FakeGFEngine(
        status_payload={
            "loaded": False,
            "pgf_path": "gf/semantik_architect.pgf",
            "error": "missing binary",
        }
    )
    adapter = GFConstructionAdapter(engine=engine)

    plan = _plan()

    with pytest.raises(RealizationError, match="GF runtime not loaded"):
        await adapter.realize(plan)


@pytest.mark.asyncio
async def test_realize_rejects_wrapper_when_passthrough_disabled() -> None:
    adapter = GFConstructionAdapter(
        engine=FakeGFEngine(),
        allow_wrapper_passthrough=False,
    )

    plan = _plan(
        construction_id="topic_comment_copular",
        slot_map={"subject": "Marie Curie", "profession": "physicist"},
        metadata={
            "wrapper_construction_id": "topic_comment_copular",
            "base_construction_id": "copula_equative_simple",
        },
    )

    with pytest.raises(RealizationError, match="disabled for GF passthrough"):
        await adapter.realize(plan)


@pytest.mark.asyncio
async def test_realize_rejects_unsupported_construction() -> None:
    adapter = GFConstructionAdapter(engine=FakeGFEngine())

    plan = _plan(construction_id="intransitive_event")

    with pytest.raises(RealizationError, match="unsupported GF construction"):
        await adapter.realize(plan)


@pytest.mark.asyncio
async def test_realize_rejects_placeholder_linearization() -> None:
    engine = FakeGFEngine(linearize_value="<missing lexeme>")
    adapter = GFConstructionAdapter(engine=engine)

    plan = _plan()

    with pytest.raises(RealizationError, match="missing lexeme"):
        await adapter.realize(plan)


@pytest.mark.asyncio
async def test_realize_does_not_mutate_plan_slot_map() -> None:
    engine = FakeGFEngine()
    adapter = GFConstructionAdapter(engine=engine)

    plan = _plan(
        construction_id="copula_equative_classification",
        slot_map={
            "subject": "Marie Curie",
            "predicate_nominal": {"head": "physicist", "modifier": "Polish"},
        },
        lexical_bindings={"profession": "physicist"},
        generation_options={"allow_fallback": True},
    )
    before = plan.to_dict(include_empty=True)

    await adapter.realize(plan)

    after = plan.to_dict(include_empty=True)
    assert after == before