import json
from pathlib import Path

import pytest

from app.adapters.engines.family_construction_adapter import (
    FamilyConstructionAdapter,
    FamilyRendererError,
    MissingRequiredRoleError,
    UnsupportedConstructionError,
)
from app.core.domain.exceptions import LanguageNotFoundError
from app.core.domain.planning.construction_plan import ConstructionPlan


@pytest.fixture
def build_family_adapter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    counter = {"value": 0}

    def _write_text(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def _write_json(path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _build(
        *,
        lang_code: str = "en",
        family: str = "germanic",
        profile_extra: dict | None = None,
        config_payload: dict | None = None,
        module_bodies: dict[str, str] | None = None,
    ) -> FamilyConstructionAdapter:
        counter["value"] += 1
        case_root = tmp_path / f"case_{counter['value']}"
        repo_root = case_root / "repo"
        pkg_root = case_root / "pkg"
        package_name = f"test_family_engines_{counter['value']}"

        monkeypatch.syspath_prepend(str(pkg_root))

        _write_text(pkg_root / package_name / "__init__.py", "")

        default_module_bodies = {
            "germanic": """
def render_bio(name, gender, prof_lemma, nat_lemma, config):
    nat = f"{nat_lemma} " if nat_lemma else ""
    marker = config.get("engine_marker", "germanic")
    return f"{name} is a {nat}{prof_lemma} [{marker}|{gender}]"
""",
            "analytic": """
def render_bio(name, gender, prof_lemma, nat_lemma, config):
    nat = f"{nat_lemma} " if nat_lemma else ""
    marker = config.get("engine_marker", "analytic")
    return f"ANALYTIC::{name}::{gender}::{nat}{prof_lemma}::{marker}"
""",
        }

        effective_bodies = {**default_module_bodies, **(module_bodies or {})}
        for module_name, source in effective_bodies.items():
            _write_text(pkg_root / package_name / f"{module_name}.py", source.strip() + "\n")

        profile = {
            "name": f"Test-{lang_code}",
            "language_code": lang_code,
            "family": family,
            "morphology_family": family,
        }
        if profile_extra:
            profile.update(profile_extra)

        profiles_path = repo_root / "app" / "core" / "config" / "profiles" / "profiles.json"
        _write_json(profiles_path, {lang_code: profile})

        config_payload = {
            "template_id": f"{lang_code}-{family}-bio",
            "engine_marker": f"{family}-marker",
            **(config_payload or {}),
        }

        family_config_path = repo_root / "data" / family / f"{lang_code}.json"
        _write_json(family_config_path, config_payload)

        if family in {"agglutinative", "uralic"}:
            alias_config_path = repo_root / "data" / "analytic" / f"{lang_code}.json"
            _write_json(alias_config_path, config_payload)

        return FamilyConstructionAdapter(
            engine_package=package_name,
            profiles_path=profiles_path,
            repo_root=repo_root,
        )

    return _build


def _make_plan(
    *,
    construction_id: str = "copula_equative_classification",
    lang_code: str = "en",
    slot_map: dict,
    lexical_bindings: dict | None = None,
    generation_options: dict | None = None,
    metadata: dict | None = None,
) -> ConstructionPlan:
    return ConstructionPlan(
        construction_id=construction_id,
        lang_code=lang_code,
        slot_map=slot_map,
        lexical_bindings=lexical_bindings or {},
        generation_options=generation_options or {},
        metadata=metadata or {},
    )


def test_supports_and_support_status_follow_construction_and_language_contract(
    build_family_adapter,
):
    adapter = build_family_adapter()

    assert adapter.backend_name == "family"
    assert adapter.supports("copula_equative_classification", "en") is True
    assert adapter.get_support_status("copula_equative_classification", "en") == "full"

    assert adapter.supports("intransitive_event", "en") is False
    assert adapter.get_support_status("intransitive_event", "en") == "partial"

    assert adapter.supports("copula_equative_classification", "zz") is False
    assert adapter.get_support_status("copula_equative_classification", "zz") == "unsupported"


@pytest.mark.asyncio
async def test_realize_success_prefers_lexical_bindings_and_emits_structured_metadata(
    build_family_adapter,
):
    adapter = build_family_adapter()

    plan = _make_plan(
        slot_map={
            "subject": {
                "name": "Marie Curie",
                "gender": "female",
            },
        },
        lexical_bindings={
            "profession": {"lemma": "physicist"},
            "nationality": {"lemma": "Polish"},
        },
        metadata={
            "wrapper_construction_id": "biography_lead",
            "base_construction_id": "copula_equative_classification",
        },
    )

    result = await adapter.realize(plan)

    assert result.text == "Marie Curie is a Polish physicist [germanic-marker|female]"
    assert result.lang_code == "en"
    assert result.construction_id == "copula_equative_classification"
    assert result.renderer_backend == "family"
    assert result.fallback_used is False
    assert result.tokens == result.text.split()

    debug = result.debug_info
    assert debug["construction_id"] == "copula_equative_classification"
    assert debug["renderer_backend"] == "family"
    assert debug["selected_backend"] == "family"
    assert debug["attempted_backends"] == ["family"]
    assert debug["resolved_language"] == "en"
    assert debug["family"] == "germanic"
    assert debug["template_id"] == "en-germanic-bio"
    assert debug["wrapper_construction_id"] == "biography_lead"
    assert debug["base_construction_id"] == "copula_equative_classification"
    assert debug["fallback_used"] is False
    assert debug["lexical_sources"]["subject"] == "slot:subject.name"
    assert debug["lexical_sources"]["gender"] == "slot:subject.gender"
    assert debug["lexical_sources"]["profession"] == "binding:profession"
    assert debug["lexical_sources"]["nationality"] == "binding:nationality"
    assert "assembled family surface" in debug["backend_trace"]


@pytest.mark.asyncio
async def test_realize_uses_slot_fallback_and_marks_fallback_explicitly(
    build_family_adapter,
):
    adapter = build_family_adapter()

    plan = _make_plan(
        slot_map={
            "subject": {"name": "Alan Turing"},
            "profession": "mathematician",
            "nationality": "British",
        },
    )

    result = await adapter.realize(plan)

    assert result.text == "Alan Turing is a British mathematician [germanic-marker|male]"
    assert result.fallback_used is True

    debug = result.debug_info
    assert debug["fallback_used"] is True
    assert "fallback_reason" in debug
    assert debug["lexical_sources"]["profession"] == "slot:profession"
    assert debug["lexical_sources"]["nationality"] == "slot:nationality"
    assert debug["lexical_sources"]["gender"] == "default:male"
    assert "subject gender missing; defaulted to masculine morphology" in debug["warnings"]


@pytest.mark.asyncio
async def test_realize_rejects_slot_fallback_when_allow_fallback_is_false(
    build_family_adapter,
):
    adapter = build_family_adapter()

    plan = _make_plan(
        slot_map={
            "subject": {"name": "Ada Lovelace"},
            "profession": "mathematician",
        },
        generation_options={"allow_fallback": False},
    )

    with pytest.raises(FamilyRendererError, match="allow_fallback"):
        await adapter.realize(plan)


@pytest.mark.asyncio
async def test_realize_raises_missing_required_role_for_missing_subject(
    build_family_adapter,
):
    adapter = build_family_adapter()

    plan = _make_plan(
        slot_map={
            "profession": "scientist",
        },
    )

    with pytest.raises(MissingRequiredRoleError, match="subject"):
        await adapter.realize(plan)


@pytest.mark.asyncio
async def test_realize_raises_unsupported_construction_for_out_of_scope_plan(
    build_family_adapter,
):
    adapter = build_family_adapter()

    plan = _make_plan(
        construction_id="intransitive_event",
        slot_map={
            "subject": {"name": "Marie Curie"},
            "profession": "physicist",
        },
    )

    with pytest.raises(UnsupportedConstructionError, match="intransitive_event"):
        await adapter.realize(plan)


@pytest.mark.asyncio
async def test_realize_raises_language_not_found_for_unknown_profile(
    build_family_adapter,
):
    adapter = build_family_adapter()

    plan = _make_plan(
        lang_code="zz",
        slot_map={
            "subject": {"name": "Grace Hopper"},
            "profession": "computer scientist",
        },
    )

    with pytest.raises(LanguageNotFoundError):
        await adapter.realize(plan)


@pytest.mark.asyncio
async def test_realize_is_deterministic_and_does_not_mutate_shared_plan_state(
    build_family_adapter,
):
    adapter = build_family_adapter()

    plan = _make_plan(
        slot_map={
            "subject": {"name": "Katherine Johnson", "gender": "female"},
        },
        lexical_bindings={
            "profession": {"lemma": "mathematician"},
            "nationality": {"lemma": "American"},
        },
        metadata={
            "wrapper_construction_id": "biography_lead",
            "base_construction_id": "copula_equative_classification",
        },
    )
    before = plan.to_dict(include_empty=True)

    first = await adapter.realize(plan)
    second = await adapter.realize(plan)

    after = plan.to_dict(include_empty=True)

    assert first.text == second.text
    assert first.tokens == second.tokens
    assert first.debug_info["lexical_sources"] == second.debug_info["lexical_sources"]
    assert before == after


@pytest.mark.asyncio
async def test_family_alias_mapping_loads_analytic_module_for_agglutinative_profile(
    build_family_adapter,
):
    adapter = build_family_adapter(lang_code="tr", family="agglutinative")

    plan = _make_plan(
        lang_code="tr",
        slot_map={
            "subject": {"name": "Test Subject", "gender": "female"},
        },
        lexical_bindings={
            "profession": {"lemma": "engineer"},
        },
    )

    result = await adapter.realize(plan)

    assert result.text == "ANALYTIC::Test Subject::female::engineer::agglutinative-marker"
    assert result.renderer_backend == "family"
    assert result.debug_info["family"] == "agglutinative"
    assert result.debug_info["selected_backend"] == "family"