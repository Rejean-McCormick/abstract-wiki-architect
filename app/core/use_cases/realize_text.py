# app/core/use_cases/realize_text.py
from __future__ import annotations

import inspect
from dataclasses import dataclass, field, is_dataclass, replace
from typing import TYPE_CHECKING, Any
from collections.abc import Iterable, Mapping, Sequence

import structlog

from app.core.domain.exceptions import DomainError
from app.shared.observability import get_tracer

logger = structlog.get_logger()
tracer = get_tracer(__name__)

if TYPE_CHECKING:
    from app.core.domain.planning.construction_plan import ConstructionPlan
    from app.core.ports.lexical_resolver_port import LexicalResolverPort
    from app.core.ports.realizer_port import RealizerPort


# ---------------------------------------------------------------------------
# Fallback domain errors
# ---------------------------------------------------------------------------

try:
    from app.core.domain.exceptions import ConstructionPlanError  # type: ignore
except ImportError:
    class ConstructionPlanError(DomainError):
        """Raised when a ConstructionPlan is malformed or incomplete."""

        def __init__(self, reason: str):
            super().__init__(f"Invalid ConstructionPlan: {reason}")


try:
    from app.core.domain.exceptions import LexicalResolutionError  # type: ignore
except ImportError:
    class LexicalResolutionError(DomainError):
        """Raised when slot-map lexical normalization fails."""

        def __init__(self, reason: str):
            super().__init__(f"Lexical resolution failed: {reason}")


try:
    from app.core.domain.exceptions import RealizationError  # type: ignore
except ImportError:
    class RealizationError(DomainError):
        """Raised when the backend realizer cannot produce surface text."""

        def __init__(self, reason: str):
            super().__init__(f"Realization failed: {reason}")


# ---------------------------------------------------------------------------
# Fallback SurfaceResult contract
# ---------------------------------------------------------------------------

try:
    from app.core.domain.models import SurfaceResult as _ImportedSurfaceResult  # type: ignore
except Exception:
    _ImportedSurfaceResult = None


@dataclass(frozen=True, slots=True)
class _FallbackSurfaceResult:
    """
    Local fallback result contract used until app.core.domain.models exports
    a canonical SurfaceResult object.
    """
    text: str
    lang_code: str
    construction_id: str
    renderer_backend: str
    fallback_used: bool = False
    tokens: tuple[str, ...] = field(default_factory=tuple)
    debug_info: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _coerce_string(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string, got {type(value).__name__}")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


def _get_value(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _as_plain_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return {str(k): v for k, v in value.items()}
    return {}


def _normalize_tokens(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()

    if isinstance(value, str):
        stripped = value.strip()
        return (stripped,) if stripped else ()

    if isinstance(value, Sequence):
        tokens: list[str] = []
        for item in value:
            if isinstance(item, str):
                token = item.strip()
                if token:
                    tokens.append(token)
        return tuple(tokens)

    return ()


def _infer_renderer_backend(result: Any, realizer: Any, debug_info: Mapping[str, Any]) -> str:
    for candidate in (
        _get_value(result, "renderer_backend"),
        debug_info.get("renderer_backend"),
        getattr(realizer, "renderer_backend", None),
        getattr(realizer, "backend_name", None),
    ):
        if _is_non_empty_string(candidate):
            return str(candidate).strip()
    return "unknown"


def _build_result_object(
    *,
    text: str,
    lang_code: str,
    construction_id: str,
    renderer_backend: str,
    fallback_used: bool,
    tokens: tuple[str, ...],
    debug_info: dict[str, Any],
) -> Any:
    """
    Construct the canonical SurfaceResult if available; otherwise fall back
    to the local compatible dataclass.
    """
    if _ImportedSurfaceResult is not None:
        try:
            return _ImportedSurfaceResult(
                text=text,
                lang_code=lang_code,
                construction_id=construction_id,
                renderer_backend=renderer_backend,
                fallback_used=fallback_used,
                tokens=list(tokens),
                debug_info=debug_info,
            )
        except TypeError:
            # Future models may temporarily differ; preserve the contract here.
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


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _extract_slot_map(construction_plan: Any) -> Any:
    return _get_value(construction_plan, "slot_map")


def _extract_lexical_bindings(slot_map: Any) -> Any:
    if isinstance(slot_map, Mapping):
        return slot_map.get("lexical_bindings")
    return getattr(slot_map, "lexical_bindings", None)


def _clone_with_updates(obj: Any, **changes: Any) -> Any:
    """
    Best-effort immutable update helper.

    Supported shapes:
    - mapping/dict
    - custom domain objects with `.with_updates(**changes)`
    - Pydantic v2 models with `.model_copy(update=...)`
    - dataclasses
    - namedtuple-like objects with `._replace(**changes)`
    - plain objects reconstructible from `vars(obj)`
    """
    if not changes:
        return obj

    if isinstance(obj, Mapping):
        merged = dict(obj)
        merged.update(changes)
        return merged

    if hasattr(obj, "with_updates") and callable(obj.with_updates):
        return obj.with_updates(**changes)

    model_copy = getattr(obj, "model_copy", None)
    if callable(model_copy):
        return model_copy(update=changes)

    if is_dataclass(obj) and not isinstance(obj, type):
        return replace(obj, **changes)

    replacer = getattr(obj, "_replace", None)
    if callable(replacer):
        return replacer(**changes)

    if hasattr(obj, "__dict__"):
        payload = dict(vars(obj))
        payload.update(changes)
        try:
            return obj.__class__(**payload)
        except TypeError as exc:
            raise ConstructionPlanError(
                f"Could not clone plan of type {obj.__class__.__name__} with updates: {exc}"
            ) from exc

    raise ConstructionPlanError(
        f"Unsupported ConstructionPlan object type: {type(obj).__name__}"
    )


# ---------------------------------------------------------------------------
# Use case
# ---------------------------------------------------------------------------

class RealizeText:
    """
    Use case: realize a validated ConstructionPlan into surface text.

    Responsibilities:
    1. Validate the incoming ConstructionPlan contract.
    2. Optionally resolve slot values through a lexical resolver.
    3. Delegate surface generation to the configured realizer backend.
    4. Normalize the returned SurfaceResult shape and debug metadata.
    5. Preserve plan immutability by cloning instead of mutating.
    """

    def __init__(
        self,
        realizer: "RealizerPort",
        lexical_resolver: "LexicalResolverPort | None" = None,
    ) -> None:
        if realizer is None or not hasattr(realizer, "realize"):
            raise TypeError("realizer must implement a 'realize(construction_plan)' method")

        if lexical_resolver is not None and not hasattr(lexical_resolver, "resolve_slot_map"):
            raise TypeError(
                "lexical_resolver must implement 'resolve_slot_map(slot_map, *, lang_code=...)'"
            )

        self.realizer = realizer
        self.lexical_resolver = lexical_resolver

    async def execute(self, construction_plan: "ConstructionPlan") -> Any:
        """
        Realize a single ConstructionPlan.

        Returns a canonical SurfaceResult-compatible object.
        """
        plan = self._validate_construction_plan(construction_plan)
        construction_id = _get_value(plan, "construction_id")
        lang_code = _get_value(plan, "lang_code")

        with tracer.start_as_current_span("use_case.realize_text") as span:
            span.set_attribute("app.lang_code", lang_code)
            span.set_attribute("app.construction_id", construction_id)

            logger.info(
                "realization_started",
                lang_code=lang_code,
                construction_id=construction_id,
                lexical_resolution=bool(self.lexical_resolver),
            )

            try:
                resolved_plan, resolution_info = await self._apply_lexical_resolution(plan)
                raw_result = await _maybe_await(self.realizer.realize(resolved_plan))
                normalized = self._normalize_surface_result(
                    raw_result,
                    resolved_plan,
                    resolution_info=resolution_info,
                )

                logger.info(
                    "realization_completed",
                    lang_code=normalized.lang_code,
                    construction_id=normalized.construction_id,
                    renderer_backend=normalized.renderer_backend,
                    fallback_used=bool(normalized.fallback_used),
                )

                return normalized

            except DomainError:
                raise
            except Exception as exc:
                logger.error(
                    "realization_failed",
                    lang_code=lang_code,
                    construction_id=construction_id,
                    error=str(exc),
                    exc_info=True,
                )
                raise RealizationError(
                    f"Could not realize construction '{construction_id}' for language "
                    f"'{lang_code}': {exc}"
                ) from exc

    async def execute_many(self, construction_plans: Iterable["ConstructionPlan"]) -> list[Any]:
        """
        Realize multiple plans sequentially and deterministically.

        Sequential execution is intentional here: it preserves ordering and
        avoids incidental backend/caching behavior differences during the
        migration phase.
        """
        if construction_plans is None:
            raise ConstructionPlanError("construction_plans must not be None")

        results: list[Any] = []
        for index, plan in enumerate(construction_plans):
            try:
                results.append(await self.execute(plan))
            except DomainError:
                raise
            except Exception as exc:
                raise RealizationError(
                    f"Failed to realize sentence at index {index}: {exc}"
                ) from exc
        return results

    __call__ = execute

    def _validate_construction_plan(self, construction_plan: Any) -> Any:
        if construction_plan is None:
            raise ConstructionPlanError("construction_plan must not be None")

        construction_id = _get_value(construction_plan, "construction_id")
        lang_code = _get_value(construction_plan, "lang_code")
        slot_map = _extract_slot_map(construction_plan)

        try:
            _coerce_string(construction_id, field_name="construction_id")
        except Exception as exc:
            raise ConstructionPlanError(str(exc)) from exc

        try:
            _coerce_string(lang_code, field_name="lang_code")
        except Exception as exc:
            raise ConstructionPlanError(str(exc)) from exc

        if slot_map is None:
            raise ConstructionPlanError("slot_map must be present and non-null")

        return construction_plan

    async def _apply_lexical_resolution(self, construction_plan: Any) -> tuple[Any, dict[str, Any]]:
        if self.lexical_resolver is None:
            return construction_plan, {
                "applied": False,
                "resolver": None,
            }

        lang_code = _get_value(construction_plan, "lang_code")
        slot_map = _extract_slot_map(construction_plan)

        try:
            resolved_slot_map = await _maybe_await(
                self.lexical_resolver.resolve_slot_map(slot_map, lang_code=lang_code)
            )
        except DomainError:
            raise
        except Exception as exc:
            raise LexicalResolutionError(str(exc)) from exc

        if resolved_slot_map is None:
            raise LexicalResolutionError("resolver returned None for slot_map")

        updated_plan = construction_plan
        if resolved_slot_map is not slot_map:
            updated_plan = _clone_with_updates(updated_plan, slot_map=resolved_slot_map)

        lexical_bindings = _extract_lexical_bindings(resolved_slot_map)
        if lexical_bindings is not None:
            try:
                updated_plan = _clone_with_updates(updated_plan, lexical_bindings=lexical_bindings)
            except ConstructionPlanError:
                # Some plan objects may not expose lexical_bindings directly yet.
                pass

        return updated_plan, {
            "applied": True,
            "resolver": self.lexical_resolver.__class__.__name__,
        }

    def _normalize_surface_result(
        self,
        raw_result: Any,
        construction_plan: Any,
        *,
        resolution_info: Mapping[str, Any],
    ) -> Any:
        if raw_result is None:
            raise RealizationError("realizer returned None")

        construction_id = _coerce_string(
            _get_value(construction_plan, "construction_id"),
            field_name="construction_id",
        )
        plan_lang_code = _coerce_string(
            _get_value(construction_plan, "lang_code"),
            field_name="lang_code",
        )

        text = _get_value(raw_result, "text")
        if not _is_non_empty_string(text):
            if isinstance(raw_result, str) and raw_result.strip():
                text = raw_result.strip()
            else:
                raise RealizationError(
                    "realizer result must expose a non-empty 'text' field"
                )

        lang_code = _get_value(raw_result, "lang_code", plan_lang_code)
        if not _is_non_empty_string(lang_code):
            lang_code = plan_lang_code
        lang_code = str(lang_code).strip()

        existing_debug = _as_plain_dict(_get_value(raw_result, "debug_info", {}))
        renderer_backend = _infer_renderer_backend(raw_result, self.realizer, existing_debug)

        fallback_used_raw = _get_value(
            raw_result,
            "fallback_used",
            existing_debug.get("fallback_used", False),
        )
        fallback_used = bool(fallback_used_raw)

        tokens = _normalize_tokens(_get_value(raw_result, "tokens"))

        debug_info = dict(existing_debug)
        debug_info.setdefault("construction_id", construction_id)
        debug_info.setdefault("renderer_backend", renderer_backend)
        debug_info.setdefault("lang_code", lang_code)
        debug_info.setdefault("fallback_used", fallback_used)

        if "selected_backend" not in debug_info and renderer_backend != "unknown":
            debug_info["selected_backend"] = renderer_backend

        if "attempted_backends" not in debug_info and renderer_backend != "unknown":
            debug_info["attempted_backends"] = [renderer_backend]

        if resolution_info.get("applied"):
            existing_lr = debug_info.get("lexical_resolution")
            if isinstance(existing_lr, Mapping):
                merged_lr = dict(existing_lr)
                for key, value in resolution_info.items():
                    merged_lr.setdefault(key, value)
                debug_info["lexical_resolution"] = merged_lr
            else:
                debug_info["lexical_resolution"] = dict(resolution_info)

        if not tokens and isinstance(text, str):
            tokens = tuple(part for part in text.split() if part)

        return _build_result_object(
            text=str(text).strip(),
            lang_code=lang_code,
            construction_id=construction_id,
            renderer_backend=renderer_backend,
            fallback_used=fallback_used,
            tokens=tokens,
            debug_info=debug_info,
        )


__all__ = [
    "RealizeText",
    "ConstructionPlanError",
    "LexicalResolutionError",
    "RealizationError",
]