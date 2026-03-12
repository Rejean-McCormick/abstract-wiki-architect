from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import structlog

from app.adapters.engines.gf_wrapper import GFGrammarEngine
from app.core.domain.exceptions import DomainError
from app.core.domain.models import SurfaceResult
from app.core.domain.planning.construction_plan import ConstructionPlan


try:
    from app.core.domain.exceptions import RealizationError  # type: ignore
except Exception:  # pragma: no cover - staged migration safety
    class RealizationError(DomainError):
        """Raised when the GF backend cannot realize a ConstructionPlan."""

        def __init__(self, reason: str):
            super().__init__(f"GF realization failed: {reason}")


logger = structlog.get_logger()

_GF_DIRECT_CONSTRUCTIONS = frozenset(
    {
        "copula_equative_simple",
        "copula_equative_classification",
        "bio_lead_identity",
    }
)
_GF_WRAPPER_CONSTRUCTIONS = frozenset({"topic_comment_copular"})


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _clean_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_construction_id(value: Any) -> str:
    text = _clean_string(value)
    if not text:
        raise RealizationError("construction_id must be a non-empty string")
    return text.lower().replace("-", "_").replace(" ", "_")


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _slot_keys(plan: ConstructionPlan) -> list[str]:
    try:
        return list(plan.slot_keys)
    except Exception:
        return [str(k) for k in _as_mapping(getattr(plan, "slot_map", {})).keys()]


def _first_non_empty_string(*values: Any) -> str | None:
    for value in values:
        text = _extract_text(value)
        if text:
            return text
    return None


def _extract_text(value: Any) -> str | None:
    if value is None:
        return None

    if isinstance(value, str):
        return _clean_string(value)

    if isinstance(value, Mapping):
        preferred_keys = (
            "label",
            "name",
            "text",
            "surface",
            "value",
            "lemma",
            "title",
            "display",
            "word",
        )
        for key in preferred_keys:
            candidate = value.get(key)
            if _is_non_empty_string(candidate):
                return str(candidate).strip()

        for nested_key in ("entity", "ref", "value_obj", "lexeme", "head", "subject"):
            nested = value.get(nested_key)
            nested_text = _extract_text(nested)
            if nested_text:
                return nested_text

        return None

    return None


def _extract_subject_text(plan: ConstructionPlan) -> str | None:
    slot_map = _as_mapping(plan.slot_map)
    lexical_bindings = _as_mapping(plan.lexical_bindings)
    metadata = _as_mapping(plan.metadata)

    return _first_non_empty_string(
        slot_map.get("subject"),
        lexical_bindings.get("subject"),
        metadata.get("subject"),
        slot_map.get("topic"),
    )


def _extract_profession_text(plan: ConstructionPlan) -> str | None:
    slot_map = _as_mapping(plan.slot_map)
    lexical_bindings = _as_mapping(plan.lexical_bindings)

    predicate_nominal = _as_mapping(slot_map.get("predicate_nominal"))

    return _first_non_empty_string(
        slot_map.get("profession"),
        lexical_bindings.get("profession"),
        predicate_nominal.get("profession"),
        predicate_nominal.get("head"),
        predicate_nominal.get("nominal"),
        predicate_nominal.get("predicate"),
    )


def _extract_nationality_text(plan: ConstructionPlan) -> str | None:
    slot_map = _as_mapping(plan.slot_map)
    lexical_bindings = _as_mapping(plan.lexical_bindings)

    predicate_nominal = _as_mapping(slot_map.get("predicate_nominal"))

    return _first_non_empty_string(
        slot_map.get("nationality"),
        lexical_bindings.get("nationality"),
        predicate_nominal.get("nationality"),
        predicate_nominal.get("modifier"),
        predicate_nominal.get("adjective"),
    )


class GFConstructionAdapter:
    """
    ConstructionPlan -> SurfaceResult adapter for the GF backend.

    This first runtime slice is intentionally conservative:
    it realizes the current copular / bio-shaped constructions through the
    shared GF grammar surface (`mkBioProf`, `mkBioNat`, `mkBioFull`) while
    preserving the canonical construction contract.

    Unsupported constructions fail explicitly rather than silently routing into
    a different semantic path.
    """

    backend_name = "gf"
    renderer_backend = "gf"

    def __init__(
        self,
        engine: GFGrammarEngine | None = None,
        *,
        allow_wrapper_passthrough: bool = True,
    ) -> None:
        self.engine = engine or GFGrammarEngine()
        self.allow_wrapper_passthrough = bool(allow_wrapper_passthrough)

    def supports(self, construction_id: str, lang_code: str) -> bool:
        _ = lang_code  # reserved for future language-aware capability tables
        cid = _normalize_construction_id(construction_id)
        return cid in _GF_DIRECT_CONSTRUCTIONS or (
            self.allow_wrapper_passthrough and cid in _GF_WRAPPER_CONSTRUCTIONS
        )

    def get_support_status(self, construction_id: str, lang_code: str) -> str:
        _ = lang_code
        cid = _normalize_construction_id(construction_id)
        if cid in _GF_DIRECT_CONSTRUCTIONS:
            return "full"
        if self.allow_wrapper_passthrough and cid in _GF_WRAPPER_CONSTRUCTIONS:
            return "partial"
        return "unsupported"

    async def realize(self, construction_plan: ConstructionPlan) -> SurfaceResult:
        if not isinstance(construction_plan, ConstructionPlan):
            raise TypeError("GFConstructionAdapter.realize expects a ConstructionPlan")

        construction_plan.validate()

        construction_id = _normalize_construction_id(construction_plan.construction_id)
        effective_construction_id = construction_id
        fallback_used = False
        backend_trace = ["validated_construction_plan"]

        if construction_plan.is_wrapper_plan:
            wrapper_id = _normalize_construction_id(
                construction_plan.wrapper_construction_id or construction_id
            )
            base_id = _normalize_construction_id(construction_plan.base_construction_id)
            if wrapper_id in _GF_WRAPPER_CONSTRUCTIONS:
                if not self.allow_wrapper_passthrough:
                    raise RealizationError(
                        f"wrapper construction {wrapper_id!r} is disabled for GF passthrough"
                    )
                if base_id not in _GF_DIRECT_CONSTRUCTIONS:
                    raise RealizationError(
                        f"wrapper construction {wrapper_id!r} requires a GF-supported base construction"
                    )
                effective_construction_id = base_id
                fallback_used = True
                backend_trace.append("wrapper_passthrough_to_base_construction")
            else:
                raise RealizationError(f"unsupported GF wrapper construction: {wrapper_id!r}")

        elif construction_id not in _GF_DIRECT_CONSTRUCTIONS:
            raise RealizationError(f"unsupported GF construction: {construction_id!r}")

        status = None
        if hasattr(self.engine, "status"):
            try:
                status = await self.engine.status()
            except Exception as exc:  # pragma: no cover - defensive only
                logger.warning("gf_construction_status_failed", error=str(exc))

        if isinstance(status, Mapping) and not status.get("loaded", False):
            raise RealizationError(
                f"GF runtime not loaded (pgf_path={status.get('pgf_path')!r}, "
                f"error={status.get('error')!r})"
            )

        ast, trace_updates, local_fallback = self._plan_to_ast(
            construction_plan,
            effective_construction_id=effective_construction_id,
        )
        backend_trace.extend(trace_updates)
        fallback_used = fallback_used or local_fallback

        resolved_language = self._resolve_language(construction_plan.lang_code)
        text = self.engine.linearize(ast, construction_plan.lang_code)
        backend_trace.append("linearized_ast")

        if not _is_non_empty_string(text):
            raise RealizationError("GF linearization returned an empty surface string")

        stripped_text = str(text).strip()
        if stripped_text.startswith("<") and stripped_text.endswith(">"):
            raise RealizationError(stripped_text[1:-1])

        debug_info: dict[str, Any] = {
            "construction_id": construction_plan.construction_id,
            "renderer_backend": self.renderer_backend,
            "lang_code": construction_plan.lang_code,
            "resolved_language": resolved_language,
            "selected_backend": self.renderer_backend,
            "attempted_backends": [self.renderer_backend],
            "fallback_used": fallback_used,
            "slot_keys": _slot_keys(construction_plan),
            "ast": ast,
            "effective_construction_id": effective_construction_id,
            "capability_tier": self.get_support_status(
                construction_plan.construction_id,
                construction_plan.lang_code,
            ),
            "backend_trace": backend_trace,
        }

        if construction_plan.is_wrapper_plan:
            debug_info["wrapper_construction_id"] = construction_plan.wrapper_construction_id
            debug_info["base_construction_id"] = construction_plan.base_construction_id

        lexical_keys = sorted(_as_mapping(construction_plan.lexical_bindings).keys())
        if lexical_keys:
            debug_info["lexical_binding_keys"] = lexical_keys

        return SurfaceResult(
            text=stripped_text,
            lang_code=construction_plan.lang_code,
            construction_id=construction_plan.construction_id,
            renderer_backend=self.renderer_backend,
            fallback_used=fallback_used,
            tokens=stripped_text.split(),
            debug_info=debug_info,
        )

    def _resolve_language(self, lang_code: str) -> str | None:
        resolver = getattr(self.engine, "_resolve_concrete_name", None)
        if callable(resolver):
            try:
                return resolver(lang_code)
            except Exception:  # pragma: no cover - defensive only
                return None
        return None

    def _plan_to_ast(
        self,
        plan: ConstructionPlan,
        *,
        effective_construction_id: str,
    ) -> tuple[str, list[str], bool]:
        if effective_construction_id not in _GF_DIRECT_CONSTRUCTIONS:
            raise RealizationError(
                f"construction {effective_construction_id!r} is not mapped to a GF AST"
            )

        subject_text = _extract_subject_text(plan)
        if not subject_text:
            raise RealizationError("GF construction requires a subject label/name")

        profession_text = _extract_profession_text(plan)
        nationality_text = _extract_nationality_text(plan)

        fallback_used = False
        trace = ["mapped_slot_map_to_gf_arguments"]

        if not profession_text and not nationality_text:
            allow_fallback = bool(_as_mapping(plan.generation_options).get("allow_fallback", True))
            if not allow_fallback:
                raise RealizationError(
                    "missing profession/nationality content and allow_fallback is disabled"
                )
            profession_text = "person"
            fallback_used = True
            trace.append("defaulted_missing_predicate_nominal_to_person")

        subject_expr = f'mkEntityStr "{self._escape_gf_string(subject_text)}"'

        if profession_text and nationality_text:
            prof_expr = f'strProf "{self._escape_gf_string(profession_text)}"'
            nat_expr = f'strNat "{self._escape_gf_string(nationality_text)}"'
            trace.append("selected_mkBioFull")
            return (
                f"mkBioFull ({subject_expr}) ({prof_expr}) ({nat_expr})",
                trace,
                fallback_used,
            )

        if nationality_text and not profession_text:
            nat_expr = f'strNat "{self._escape_gf_string(nationality_text)}"'
            trace.append("selected_mkBioNat")
            return f"mkBioNat ({subject_expr}) ({nat_expr})", trace, fallback_used

        prof_expr = f'strProf "{self._escape_gf_string(profession_text or "person")}"'
        trace.append("selected_mkBioProf")
        return f"mkBioProf ({subject_expr}) ({prof_expr})", trace, fallback_used

    @staticmethod
    def _escape_gf_string(value: str) -> str:
        return (value or "").replace("\\", "\\\\").replace('"', '\\"')


__all__ = ["GFConstructionAdapter"]