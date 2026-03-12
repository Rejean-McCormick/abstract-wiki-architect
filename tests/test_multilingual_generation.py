# tests/test_multilingual_generation.py
from __future__ import annotations

import os
import sys

import pytest

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.adapters.engines.gf_wrapper import GFGrammarEngine
from app.core.domain.planning.construction_plan import ConstructionPlan


def _non_placeholder_text(text: str) -> bool:
    value = (text or "").strip()
    if not value:
        return False
    if value in {"[]", "<GF Runtime Not Loaded>", "<LinearizeError>"}:
        return False
    if value.startswith("<LinearizeError"):
        return False
    if value.startswith("<Language '") and value.endswith(">"):
        return False
    if value.startswith("<GF ") and value.endswith(">"):
        return False
    return True


def _pick_input_lang(engine: GFGrammarEngine, *candidates: str) -> str:
    for candidate in candidates:
        if engine._resolve_concrete_name(candidate):
            return candidate
    pytest.skip(f"No supported language among candidates: {candidates}")


def _bio_plan(lang_code: str) -> ConstructionPlan:
    return ConstructionPlan(
        construction_id="copula_equative_classification",
        lang_code=lang_code,
        slot_map={
            "subject": {
                "label": "Marie Curie",
                "entity_type": "person",
                "features": {"gender": "female", "human": True},
            },
            "profession": {
                "lemma": "physicist",
                "pos": "NOUN",
                "source": "test",
            },
            "nationality": {
                "lemma": "polish",
                "pos": "ADJ",
                "source": "test",
            },
            "predicate_nominal": {
                "profession": {"lemma": "physicist"},
                "nationality": {"lemma": "polish"},
            },
        },
        generation_options={"allow_fallback": True},
        lexical_bindings={
            "profession": {"lemma": "physicist", "source": "test"},
            "nationality": {"lemma": "polish", "source": "test"},
        },
        metadata={"test_case": "multilingual_generation"},
    )


@pytest.fixture(scope="module")
def gf_engine() -> GFGrammarEngine:
    """
    Initialize the GF engine once for the module.

    The suite is skipped when the PGF runtime is unavailable because these are
    integration-style grammar tests rather than pure unit tests.
    """
    engine = GFGrammarEngine()

    if not engine.grammar:
        pytest.skip(
            "GF runtime unavailable. Build/load the PGF binary before running "
            "multilingual GF generation tests."
        )

    return engine


def test_engine_languages_include_english_baseline(gf_engine: GFGrammarEngine) -> None:
    langs = sorted(gf_engine.grammar.languages.keys())
    resolved = gf_engine._resolve_concrete_name("eng")

    assert resolved is not None, f"English language resolution failed. Loaded: {langs}"
    assert resolved in langs
    assert "WikiEng" in langs or resolved.lower().endswith("eng")


def test_language_resolution_accepts_common_aliases(gf_engine: GFGrammarEngine) -> None:
    english = {gf_engine._resolve_concrete_name(code) for code in ("eng", "en", "WikiEng")}
    english.discard(None)

    assert len(english) == 1, f"English aliases resolved inconsistently: {english}"

    french_candidates = {
        gf_engine._resolve_concrete_name(code)
        for code in ("fre", "fra", "fr", "WikiFre", "WikiFra")
    }
    french_candidates.discard(None)

    # French may be absent from smaller PGF builds, so only assert consistency if present.
    if french_candidates:
        assert len(french_candidates) == 1, (
            f"French aliases resolved inconsistently: {french_candidates}"
        )


def test_literal_generation_via_legacy_ast_helper(gf_engine: GFGrammarEngine) -> None:
    lang = _pick_input_lang(gf_engine, "eng", "en", "WikiEng")
    ast_str = gf_engine._convert_to_gf_ast("Hello World", lang)

    assert '"Hello World"' in ast_str

    text = gf_engine.linearize(ast_str, lang)
    assert _non_placeholder_text(text), f"Unexpected GF output: {text!r}"
    assert "hello" in text.lower() and "world" in text.lower()


def test_transitive_event_ast_generation_and_linearization(gf_engine: GFGrammarEngine) -> None:
    lang = _pick_input_lang(gf_engine, "eng", "en", "WikiEng")
    ninai_obj = {
        "function": "mkCl",
        "args": [
            {
                "function": "mkNP",
                "args": [{"function": "mkN", "args": ["cat"]}],
            },
            {
                "function": "mkV2",
                "args": ["eat"],
            },
            {
                "function": "mkNP",
                "args": [{"function": "mkN", "args": ["fish"]}],
            },
        ],
    }

    ast_str = gf_engine._convert_to_gf_ast(ninai_obj, lang)

    for token in ("mkCl", "mkNP", "mkV2", "cat", "fish"):
        assert token in ast_str, f"Missing {token!r} in generated AST: {ast_str}"

    text = gf_engine.linearize(ast_str, lang)
    assert _non_placeholder_text(text), f"Unexpected GF output: {text!r}"
    lowered = text.lower()
    assert "cat" in lowered and "fish" in lowered


@pytest.mark.asyncio
async def test_realize_construction_plan_in_english(gf_engine: GFGrammarEngine) -> None:
    lang = _pick_input_lang(gf_engine, "eng", "en", "WikiEng")
    plan = _bio_plan(lang)

    result = await gf_engine.realize(plan)

    assert _non_placeholder_text(result.text), f"Unexpected GF output: {result.text!r}"
    assert "marie" in result.text.lower() or "curie" in result.text.lower()

    assert result.lang_code == lang.lower()
    assert result.construction_id == "copula_equative_classification"
    assert result.renderer_backend == "gf"

    debug = dict(result.debug_info or {})
    assert debug["renderer_backend"] == "gf"
    assert debug["construction_id"] == "copula_equative_classification"
    assert debug["lang_code"] == lang.lower()
    assert "resolved_language" in debug
    assert "ast" in debug and "mkBio" in str(debug["ast"])
    assert isinstance(debug.get("backend_trace"), list)
    assert debug.get("fallback_used") == result.fallback_used


@pytest.mark.asyncio
async def test_realize_construction_plan_in_french_when_available(
    gf_engine: GFGrammarEngine,
) -> None:
    lang = _pick_input_lang(gf_engine, "fre", "fra", "fr", "WikiFre", "WikiFra")
    plan = _bio_plan(lang)

    result = await gf_engine.realize(plan)

    assert _non_placeholder_text(result.text), f"Unexpected GF output: {result.text!r}"
    assert "marie" in result.text.lower() or "curie" in result.text.lower()

    debug = dict(result.debug_info or {})
    assert debug["renderer_backend"] == "gf"
    assert debug["construction_id"] == "copula_equative_classification"
    assert "resolved_language" in debug
    assert "ast" in debug and "mkBio" in str(debug["ast"])


@pytest.mark.asyncio
async def test_legacy_generate_bio_frame_remains_available_as_compatibility_shim(
    gf_engine: GFGrammarEngine,
) -> None:
    lang = _pick_input_lang(gf_engine, "eng", "en", "WikiEng")
    frame = {
        "frame_type": "bio",
        "name": "Marie Curie",
        "profession": "physicist",
        "nationality": "polish",
        "gender": "female",
    }

    result = await gf_engine.generate(lang, frame)

    assert _non_placeholder_text(result.text), f"Unexpected GF output: {result.text!r}"
    debug = dict(result.debug_info or {})
    assert debug["renderer_backend"] == "gf"
    assert debug["runtime_path"] == "legacy_direct_frame"
    assert debug["compatibility_shim"] is True
    assert "ast" in debug and "mkBio" in str(debug["ast"])
    assert "resolved_language" in debug


def test_error_handling_invalid_ninai_payload_is_strict(gf_engine: GFGrammarEngine) -> None:
    invalid_obj = {
        "missing_function_key": True,
        "args": [],
    }

    with pytest.raises(ValueError, match="Missing function attribute"):
        gf_engine._convert_to_gf_ast(invalid_obj, "eng")