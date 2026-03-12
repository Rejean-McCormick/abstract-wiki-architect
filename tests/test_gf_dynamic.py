# tests/test_gf_dynamic.py
from __future__ import annotations

from pathlib import Path

import pytest

pgf = pytest.importorskip("pgf")

from app.adapters.engines.gf_wrapper import GFGrammarEngine
from app.core.domain.planning.construction_plan import ConstructionPlan


def _select_input_lang(engine: GFGrammarEngine) -> str:
    """
    Prefer stable aliases first so we exercise the wrapper's language-resolution
    behavior, not only direct concrete names.
    """
    for candidate in ("eng", "en", "fre", "fr", "WikiEng", "WikiFre"):
        if engine._resolve_concrete_name(candidate):
            return candidate

    loaded = sorted(getattr(engine.grammar, "languages", {}).keys())
    if not loaded:
        pytest.skip("GF grammar loaded, but contains no concrete languages.")
    return loaded[0]


@pytest.fixture(scope="module")
def gf_engine() -> GFGrammarEngine:
    """
    Load the GF wrapper once for the module.

    This remains a dynamic-PGF regression test, so it skips cleanly when the PGF
    binary or Python pgf module is unavailable in the runtime.
    """
    engine = GFGrammarEngine()
    pgf_path = Path(engine.pgf_path)

    if not pgf_path.exists():
        pytest.skip(
            f"PGF binary not found at {pgf_path}. "
            "Run the GF build step before executing dynamic GF tests."
        )

    grammar = engine.grammar
    if grammar is None:
        pytest.skip(
            "GF grammar could not be loaded dynamically. "
            f"error_type={engine.last_load_error_type!r}, "
            f"error={engine.last_load_error!r}"
        )

    return engine


@pytest.mark.asyncio
async def test_gf_status_reports_loaded_runtime_and_languages(
    gf_engine: GFGrammarEngine,
) -> None:
    status = await gf_engine.status()
    supported = await gf_engine.get_supported_languages()

    assert status["loaded"] is True
    assert status["backend"] == "gf"
    assert status["language_count"] > 0
    assert Path(status["pgf_path"]).exists()

    assert supported
    assert sorted(supported) == sorted(gf_engine.grammar.languages.keys())


def test_linearize_simple_phrase_across_loaded_languages(
    gf_engine: GFGrammarEngine,
) -> None:
    """
    Smoke test the actual PGF binary directly across every loaded concrete
    syntax. This file is explicitly about dynamic loading + linearization, so an
    abstract-expression test is appropriate here.
    """
    expr = pgf.readExpr("SimpNP apple_N")

    failures: list[str] = []
    successes: list[tuple[str, str]] = []

    for lang_name in sorted(gf_engine.grammar.languages.keys()):
        text = gf_engine.linearize(expr, lang_name)

        if not text or text.startswith("<"):
            failures.append(f"{lang_name}: {text!r}")
            continue

        successes.append((lang_name, text))

    assert successes, "No loaded GF language produced a non-empty linearization."
    assert not failures, (
        "Some loaded GF languages failed to linearize a simple shared AST.\n"
        + "\n".join(failures)
    )


def test_linearize_invalid_expression_returns_stable_error_placeholder(
    gf_engine: GFGrammarEngine,
) -> None:
    lang = _select_input_lang(gf_engine)
    text = gf_engine.linearize("This Is Not Valid GF Syntax (", lang)

    assert text.startswith("<LinearizeError:"), text


@pytest.mark.asyncio
async def test_realize_bio_construction_plan_returns_surface_result_with_metadata(
    gf_engine: GFGrammarEngine,
) -> None:
    """
    Keep this file aligned with the planner-era runtime by proving the GF
    wrapper can consume ConstructionPlan directly and emits canonical metadata.
    """
    lang = _select_input_lang(gf_engine)
    resolved_language = gf_engine._resolve_concrete_name(lang)

    plan = ConstructionPlan(
        construction_id="copula_equative_classification",
        lang_code=lang,
        slot_map={
            "subject": "Marie Curie",
            "profession": "physicist",
            "nationality": "Polish",
        },
        metadata={
            "base_construction_id": "copula_equative_classification",
        },
    )

    result = await gf_engine.realize(plan)

    assert result.text
    assert not result.text.startswith("<"), result.text
    assert result.lang_code == lang
    assert result.construction_id == "copula_equative_classification"
    assert result.renderer_backend == "gf"
    assert result.fallback_used is False
    assert result.tokens

    assert result.debug_info["construction_id"] == "copula_equative_classification"
    assert result.debug_info["renderer_backend"] == "gf"
    assert result.debug_info["lang_code"] == lang
    assert result.debug_info["fallback_used"] is False
    assert result.debug_info["resolved_language"] == resolved_language
    assert set(result.debug_info["slot_keys"]) == {"subject", "profession", "nationality"}
    assert "backend_trace" in result.debug_info
    assert any(
        "constructed GF AST from ConstructionPlan" in step
        for step in result.debug_info["backend_trace"]
    )


@pytest.mark.asyncio
async def test_realize_unsupported_construction_is_explicit_fallback(
    gf_engine: GFGrammarEngine,
) -> None:
    """
    Regression guard for the migration docs: no silent success and no hidden
    backend substitution. Unsupported GF constructions must remain explicit.
    """
    lang = _select_input_lang(gf_engine)

    plan = ConstructionPlan(
        construction_id="relational_temporal_relation",
        lang_code=lang,
        slot_map={
            "left": {"name": "World War II"},
            "right": {"start_year": 1951},
            "relation": "before",
        },
    )

    result = await gf_engine.realize(plan)

    assert result.renderer_backend == "gf"
    assert result.construction_id == "relational_temporal_relation"
    assert result.fallback_used is True
    assert result.text.startswith("<GF Unsupported Construction:")
    assert result.debug_info["fallback_used"] is True
    assert result.debug_info["construction_id"] == "relational_temporal_relation"
    assert "warnings" in result.debug_info
    assert any("unsupported GF construction_id" in warning for warning in result.debug_info["warnings"])