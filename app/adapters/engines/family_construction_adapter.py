from __future__ import annotations

import importlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any
from collections.abc import Mapping

import structlog

from app.core.domain.exceptions import DomainError, LanguageNotFoundError

if TYPE_CHECKING:
    from app.core.domain.models import SurfaceResult
    from app.core.domain.planning.construction_plan import ConstructionPlan


logger = structlog.get_logger()

_BACKEND_NAME = "family"

# Migration-era supported coverage:
# - legacy biography-like plans
# - nominal-predicate / simple equative constructions that can be rendered
#   through the existing family-engine biography templates
_SUPPORTED_CONSTRUCTIONS: frozenset[str] = frozenset(
    {
        "bio",
        "biography",
        "biography_lead",
        "entity.person",
        "entity_person",
        "person",
        "copula_equative_simple",
        "copula_equative_classification",
        "copula_attributive_np",
        "topic_comment_copular",
    }
)

_ENGINE_MODULE_ALIASES: dict[str, str] = {
    # Existing engine module names do not fully match profile labels yet.
    "agglutinative": "analytic",
    "uralic": "analytic",
}


# ---------------------------------------------------------------------------
# Runtime-safe SurfaceResult import
# ---------------------------------------------------------------------------

try:
    from app.core.domain.models import SurfaceResult as _ImportedSurfaceResult
except Exception:  # pragma: no cover - import safety during staged migration
    _ImportedSurfaceResult = None


@dataclass(frozen=True, slots=True)
class _FallbackSurfaceResult:
    text: str
    lang_code: str
    construction_id: str
    renderer_backend: str
    fallback_used: bool = False
    tokens: list[str] = field(default_factory=list)
    debug_info: dict[str, Any] = field(default_factory=dict)


def _build_surface_result(
    *,
    text: str,
    lang_code: str,
    construction_id: str,
    renderer_backend: str,
    fallback_used: bool,
    tokens: list[str],
    debug_info: dict[str, Any],
) -> Any:
    if _ImportedSurfaceResult is not None:
        try:
            return _ImportedSurfaceResult(
                text=text,
                lang_code=lang_code,
                construction_id=construction_id,
                renderer_backend=renderer_backend,
                fallback_used=fallback_used,
                tokens=tokens,
                debug_info=debug_info,
            )
        except TypeError:
            pass

    return _FallbackSurfaceResult(
        text=text,
        lang_code=lang_code,
        construction_id=construction_id,
        renderer_backend=renderer_backend,
        fallback_used=fallback_used,
        tokens=tokens,
        debug_info=debug_info,
    )


# ---------------------------------------------------------------------------
# Local migration-safe exceptions
# ---------------------------------------------------------------------------


class UnsupportedConstructionError(DomainError):
    def __init__(self, construction_id: str):
        super().__init__(
            f"Construction '{construction_id}' is not supported by the family renderer."
        )


class MissingRequiredRoleError(DomainError):
    def __init__(self, role_name: str):
        super().__init__(f"Missing required role/slot for family realization: '{role_name}'.")


class FamilyRendererError(DomainError):
    def __init__(self, reason: str):
        super().__init__(f"Family renderer failed: {reason}")


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _repo_root() -> Path:
    # .../app/adapters/engines/family_construction_adapter.py -> repo root
    return Path(__file__).resolve().parents[3]


def _clean_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        return value or None
    text = str(value).strip()
    return text or None


def _as_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "to_dict") and callable(value.to_dict):
        out = value.to_dict()
        return dict(out) if isinstance(out, Mapping) else {}
    if hasattr(value, "as_dict") and callable(value.as_dict):
        out = value.as_dict()
        return dict(out) if isinstance(out, Mapping) else {}
    return {}


def _get_member(obj: Any, key: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _deep_merge(base: Mapping[str, Any], overlay: Mapping[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in overlay.items():
        if (
            key in out
            and isinstance(out[key], Mapping)
            and isinstance(value, Mapping)
        ):
            out[key] = _deep_merge(dict(out[key]), dict(value))
        else:
            out[key] = value
    return out


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("family_adapter_json_load_failed", path=str(path), error=str(exc))
        return {}
    return data if isinstance(data, dict) else {}


def _normalize_gender(value: Any) -> str:
    raw = (_clean_str(value) or "").lower()
    if raw in {"m", "male", "masc", "masculine"}:
        return "male"
    if raw in {"f", "female", "fem", "feminine"}:
        return "female"
    # Migration-safe default: current family engines generally assume
    # masculine/default morphology when gender is unavailable.
    return "male"


def _tokenize(text: str) -> list[str]:
    return [part for part in (text or "").split() if part]


def _extract_text_candidate(value: Any) -> str | None:
    """
    Best-effort text extraction from slot values / lexical bindings.
    """
    if value is None:
        return None

    if isinstance(value, str):
        return _clean_str(value)

    if isinstance(value, Mapping):
        for key in (
            "lemma",
            "label",
            "surface",
            "text",
            "name",
            "value",
            "title",
            "gloss",
        ):
            candidate = _clean_str(value.get(key))
            if candidate:
                return candidate

        features = value.get("features")
        if isinstance(features, Mapping):
            for key in ("lemma", "label", "surface", "text", "name"):
                candidate = _clean_str(features.get(key))
                if candidate:
                    return candidate

        # Common nested role layouts:
        for key in (
            "profession",
            "nationality",
            "classifier",
            "class",
            "predicate",
            "head",
        ):
            nested = _extract_text_candidate(value.get(key))
            if nested:
                return nested

        return None

    return _clean_str(value)


def _extract_subject_name(slot_map: Mapping[str, Any]) -> tuple[str | None, str]:
    for slot_name in ("subject", "main_entity", "entity", "topic", "speaker"):
        slot_value = slot_map.get(slot_name)
        if isinstance(slot_value, Mapping):
            for key in ("label", "name", "surface", "text", "title", "value"):
                candidate = _clean_str(slot_value.get(key))
                if candidate:
                    return candidate, f"slot:{slot_name}.{key}"
        candidate = _extract_text_candidate(slot_value)
        if candidate:
            return candidate, f"slot:{slot_name}"

    for key in ("subject_name", "name"):
        candidate = _extract_text_candidate(slot_map.get(key))
        if candidate:
            return candidate, f"slot:{key}"

    return None, "missing"


def _extract_subject_gender(
    slot_map: Mapping[str, Any],
    lexical_bindings: Mapping[str, Any],
) -> tuple[str, str, bool]:
    subject = slot_map.get("subject")
    if isinstance(subject, Mapping):
        for key in ("gender", "sex"):
            candidate = _clean_str(subject.get(key))
            if candidate:
                return _normalize_gender(candidate), f"slot:subject.{key}", False

        features = subject.get("features")
        if isinstance(features, Mapping):
            for key in ("gender", "sex"):
                candidate = _clean_str(features.get(key))
                if candidate:
                    return _normalize_gender(candidate), f"slot:subject.features.{key}", False

    for key in ("gender", "subject_gender"):
        candidate = _clean_str(slot_map.get(key))
        if candidate:
            return _normalize_gender(candidate), f"slot:{key}", False

    binding = lexical_bindings.get("subject") if isinstance(lexical_bindings, Mapping) else None
    if isinstance(binding, Mapping):
        for key in ("gender", "sex"):
            candidate = _clean_str(binding.get(key))
            if candidate:
                return _normalize_gender(candidate), f"binding:subject.{key}", False

    return "male", "default:male", True


def _extract_lexical_item(
    *,
    key: str,
    slot_map: Mapping[str, Any],
    lexical_bindings: Mapping[str, Any],
    slot_fallback_keys: tuple[str, ...],
) -> tuple[str | None, str]:
    binding_value = lexical_bindings.get(key) if isinstance(lexical_bindings, Mapping) else None
    binding_text = _extract_text_candidate(binding_value)
    if binding_text:
        return binding_text, f"binding:{key}"

    # Accept some common nested predicate layouts inside the slot map.
    for slot_key in slot_fallback_keys:
        slot_value = slot_map.get(slot_key)
        if isinstance(slot_value, Mapping):
            direct = _extract_text_candidate(slot_value.get(key))
            if direct:
                return direct, f"slot:{slot_key}.{key}"

            # `predicate_nominal` often acts as the container for profession/classifier.
            if key in {"profession", "classifier"}:
                direct = _extract_text_candidate(slot_value)
                if direct:
                    return direct, f"slot:{slot_key}"

        else:
            direct = _extract_text_candidate(slot_value)
            if direct:
                return direct, f"slot:{slot_key}"

    return None, "missing"


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------


class FamilyConstructionAdapter:
    """
    Migration-era family realizer adapter.

    Contract:
        ConstructionPlan -> SurfaceResult

    Current scope:
    - bridges the planner/runtime contract to the existing family engine modules
      under `app.adapters.engines.engines.*`
    - prioritizes explicitness and stable debug metadata over maximal coverage
    - currently targets biography / nominal-predicate realizations that can be
      expressed through the existing `render_bio(...)` engine surface
    """

    def __init__(
        self,
        *,
        engine_package: str = "app.adapters.engines.engines",
        profiles_path: Path | None = None,
        repo_root: Path | None = None,
    ) -> None:
        self._engine_package = engine_package
        self._repo_root = (repo_root or _repo_root()).resolve()
        self._profiles_path = (
            profiles_path
            or self._repo_root / "app" / "core" / "config" / "profiles" / "profiles.json"
        )
        self._profiles = _load_json(self._profiles_path)

    @property
    def backend_name(self) -> str:
        return _BACKEND_NAME

    def supports(self, construction_id: str, lang_code: str) -> bool:
        normalized_cid = _clean_str(construction_id) or ""
        normalized_lang = (_clean_str(lang_code) or "").lower()
        if normalized_cid not in _SUPPORTED_CONSTRUCTIONS:
            return False

        profile = self._profiles.get(normalized_lang)
        if not isinstance(profile, Mapping):
            return False

        try:
            self._load_engine_module(profile)
        except Exception:
            return False

        return True

    def get_support_status(self, construction_id: str, lang_code: str) -> str:
        if self.supports(construction_id, lang_code):
            return "full"

        normalized_lang = (_clean_str(lang_code) or "").lower()
        if normalized_lang in self._profiles:
            return "partial"

        return "unsupported"

    async def realize(self, construction_plan: "ConstructionPlan") -> "SurfaceResult":
        if construction_plan is None:
            raise FamilyRendererError("construction_plan must not be None")

        requested_construction_id = _clean_str(_get_member(construction_plan, "construction_id"))
        lang_code = (_clean_str(_get_member(construction_plan, "lang_code")) or "").lower()
        slot_map = _as_dict(_get_member(construction_plan, "slot_map"))
        generation_options = _as_dict(_get_member(construction_plan, "generation_options"))
        lexical_bindings = _as_dict(_get_member(construction_plan, "lexical_bindings"))
        metadata = _as_dict(_get_member(construction_plan, "metadata"))

        if not requested_construction_id:
            raise FamilyRendererError("construction_plan.construction_id is required")
        if not lang_code:
            raise FamilyRendererError("construction_plan.lang_code is required")
        if not slot_map:
            raise FamilyRendererError("construction_plan.slot_map must be a non-empty mapping")

        construction_id = _clean_str(metadata.get("base_construction_id")) or requested_construction_id
        wrapper_construction_id = _clean_str(metadata.get("wrapper_construction_id"))

        if construction_id not in _SUPPORTED_CONSTRUCTIONS:
            raise UnsupportedConstructionError(construction_id)

        allow_fallback = bool(generation_options.get("allow_fallback", True))

        profile = self._profiles.get(lang_code)
        if not isinstance(profile, Mapping):
            raise LanguageNotFoundError(lang_code)

        engine_module = self._load_engine_module(profile)
        render_bio = getattr(engine_module, "render_bio", None)
        if not callable(render_bio):
            raise FamilyRendererError(
                f"Engine module '{engine_module.__name__}' does not expose render_bio(...)"
            )

        config = self._load_language_config(lang_code=lang_code, profile=profile)

        trace: list[str] = ["validated construction", "validated slot_map"]
        warnings: list[str] = []

        name, name_source = _extract_subject_name(slot_map)
        if not name:
            raise MissingRequiredRoleError("subject")

        gender, gender_source, gender_defaulted = _extract_subject_gender(slot_map, lexical_bindings)
        if gender_defaulted:
            warnings.append("subject gender missing; defaulted to masculine morphology")
            trace.append("defaulted subject gender to masculine")
        else:
            trace.append("resolved subject gender")

        profession, profession_source = _extract_lexical_item(
            key="profession",
            slot_map=slot_map,
            lexical_bindings=lexical_bindings,
            slot_fallback_keys=("profession", "classifier", "class", "predicate_nominal", "predicate"),
        )
        if not profession:
            # Common classification construction often uses `classifier`.
            profession, profession_source = _extract_lexical_item(
                key="classifier",
                slot_map=slot_map,
                lexical_bindings=lexical_bindings,
                slot_fallback_keys=("classifier", "class", "predicate_nominal", "predicate"),
            )

        if not profession:
            raise MissingRequiredRoleError("profession/classifier")

        nationality, nationality_source = _extract_lexical_item(
            key="nationality",
            slot_map=slot_map,
            lexical_bindings=lexical_bindings,
            slot_fallback_keys=("nationality", "predicate_nominal", "predicate"),
        )

        lexical_sources = {
            "subject": name_source,
            "gender": gender_source,
            "profession": profession_source,
        }
        if nationality:
            lexical_sources["nationality"] = nationality_source

        lexical_fallback_used = any(
            source.startswith("slot:")
            for field_name, source in lexical_sources.items()
            if field_name in {"profession", "nationality"}
        ) or gender_defaulted

        if lexical_fallback_used and not allow_fallback:
            raise FamilyRendererError(
                "lexical fallback was required but generation_options.allow_fallback is false"
            )

        if profession_source.startswith("binding:"):
            trace.append("resolved profession lexical binding")
        else:
            trace.append("used slot fallback for profession")

        if nationality:
            if nationality_source.startswith("binding:"):
                trace.append("resolved nationality lexical binding")
            else:
                trace.append("used slot fallback for nationality")
        else:
            trace.append("nationality omitted")

        family_name = (
            _clean_str(profile.get("morphology_family"))
            or _clean_str(profile.get("family"))
            or "unknown"
        )

        try:
            surface = render_bio(
                name=name,
                gender=gender,
                prof_lemma=profession,
                nat_lemma=nationality or "",
                config=config,
            )
        except DomainError:
            raise
        except Exception as exc:
            logger.error(
                "family_render_failed",
                lang_code=lang_code,
                construction_id=construction_id,
                family=family_name,
                error=str(exc),
                exc_info=True,
            )
            raise FamilyRendererError(str(exc)) from exc

        text = _clean_str(surface)
        if not text:
            raise FamilyRendererError("family engine returned empty surface text")

        tokens = _tokenize(text)
        trace.append("assembled family surface")

        debug_info: dict[str, Any] = {
            "construction_id": requested_construction_id,
            "renderer_backend": self.backend_name,
            "lang_code": lang_code,
            "slot_keys": list(slot_map.keys()),
            "fallback_used": lexical_fallback_used,
            "requested_backend": generation_options.get("renderer_backend", self.backend_name),
            "selected_backend": self.backend_name,
            "attempted_backends": [self.backend_name],
            "family": family_name,
            "resolved_language": lang_code,
            "lexical_sources": lexical_sources,
            "backend_trace": trace,
            "surface_tokens": tokens,
            "warnings": warnings,
            "profile_name": _clean_str(profile.get("name")),
        }

        template_id = _clean_str(config.get("template_id")) or _clean_str(config.get("structure_id"))
        if template_id:
            debug_info["template_id"] = template_id

        if wrapper_construction_id:
            debug_info["wrapper_construction_id"] = wrapper_construction_id
            debug_info["base_construction_id"] = construction_id

        if lexical_fallback_used:
            debug_info["fallback_reason"] = "used slot content and/or default morphology because lexical bindings were absent or incomplete"

        logger.info(
            "family_realization_completed",
            lang_code=lang_code,
            construction_id=requested_construction_id,
            base_construction_id=construction_id,
            family=family_name,
            fallback_used=lexical_fallback_used,
        )

        return _build_surface_result(
            text=text,
            lang_code=lang_code,
            construction_id=requested_construction_id,
            renderer_backend=self.backend_name,
            fallback_used=lexical_fallback_used,
            tokens=tokens,
            debug_info=debug_info,
        )

    # ------------------------------------------------------------------
    # Internal loading helpers
    # ------------------------------------------------------------------

    def _load_engine_module(self, profile: Mapping[str, Any]) -> Any:
        family_name = (
            _clean_str(profile.get("morphology_family"))
            or _clean_str(profile.get("family"))
            or ""
        ).lower()

        if not family_name:
            raise FamilyRendererError("language profile is missing family information")

        module_name = _ENGINE_MODULE_ALIASES.get(family_name, family_name)

        try:
            return importlib.import_module(f"{self._engine_package}.{module_name}")
        except Exception as exc:
            raise FamilyRendererError(
                f"Could not import family engine module '{module_name}' for family '{family_name}': {exc}"
            ) from exc

    def _load_language_config(
        self,
        *,
        lang_code: str,
        profile: Mapping[str, Any],
    ) -> dict[str, Any]:
        """
        Merge profile + matrix + per-language card into one config dict.

        The exact data layout is still evolving, so this loader stays permissive
        and only consumes JSON files that are present.
        """
        merged: dict[str, Any] = dict(profile)

        matrix_rel = _clean_str(profile.get("morphology_config_path"))
        if matrix_rel and matrix_rel.lower().endswith(".json"):
            matrix_path = (self._repo_root / matrix_rel).resolve()
            merged = _deep_merge(merged, _load_json(matrix_path))

        family_name = (
            _clean_str(profile.get("morphology_family"))
            or _clean_str(profile.get("family"))
            or ""
        ).lower()
        module_family = _ENGINE_MODULE_ALIASES.get(family_name, family_name)

        candidates = [
            self._repo_root / "data" / module_family / f"{lang_code}.json",
            self._repo_root / "data" / family_name / f"{lang_code}.json",
            self._repo_root / "language_profiles" / f"{lang_code}.json",
        ]

        for candidate in candidates:
            if candidate.exists():
                merged = _deep_merge(merged, _load_json(candidate))
                break

        return merged


__all__ = [
    "FamilyConstructionAdapter",
    "UnsupportedConstructionError",
    "MissingRequiredRoleError",
    "FamilyRendererError",
]