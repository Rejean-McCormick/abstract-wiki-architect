# app/adapters/engines/construction_realizer.py
from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Mapping
from collections.abc import Mapping as ABCMapping, Sequence

import structlog

from app.core.domain.exceptions import DomainError

try:
    from app.core.domain.exceptions import RealizationError  # type: ignore
except ImportError:
    class RealizationError(DomainError):
        """Raised when renderer dispatch or realization fails."""

        def __init__(self, reason: str):
            super().__init__(f"Realization failed: {reason}")


try:
    from app.core.domain.models import SurfaceResult as _ImportedSurfaceResult  # type: ignore
except Exception:
    _ImportedSurfaceResult = None


if TYPE_CHECKING:
    from app.core.domain.models import SurfaceResult
    from app.core.domain.planning.construction_plan import ConstructionPlan
    from app.core.ports.realizer_port import RealizerPort, RealizerSupportStatus
else:  # pragma: no cover - import-safe during staged migration
    SurfaceResult = Any
    ConstructionPlan = Any
    RealizerPort = Any
    RealizerSupportStatus = str


logger = structlog.get_logger()

_CANONICAL_BACKEND_ORDER: tuple[str, ...] = ("gf", "family", "safe_mode")
_BACKEND_ALIASES: dict[str, str] = {
    "gf": "gf",
    "grammar": "gf",
    "grammar_engine": "gf",
    "family": "family",
    "family_engine": "family",
    "safe_mode": "safe_mode",
    "safe-mode": "safe_mode",
    "safemode": "safe_mode",
    "safe": "safe_mode",
}
_ATTEMPTABLE_STATUSES = {"full", "partial", "fallback_only"}


@dataclass(frozen=True, slots=True)
class _FallbackSurfaceResult:
    text: str
    lang_code: str
    construction_id: str
    renderer_backend: str
    fallback_used: bool = False
    tokens: tuple[str, ...] = field(default_factory=tuple)
    debug_info: dict[str, Any] = field(default_factory=dict)
    generation_time_ms: float = 0.0


def _get_value(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, ABCMapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _as_plain_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, ABCMapping):
        return {str(k): v for k, v in value.items()}
    return {}


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


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


def _normalize_backend_name(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if not normalized:
        return None
    return _BACKEND_ALIASES.get(normalized, normalized)


def _normalize_support_status(value: Any) -> str:
    if not isinstance(value, str):
        return "unsupported"
    normalized = value.strip().lower()
    if normalized in {"full", "partial", "fallback_only", "unsupported"}:
        return normalized
    return "unsupported"


def _truthy(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return default


def _build_result_object(
    *,
    text: str,
    lang_code: str,
    construction_id: str,
    renderer_backend: str,
    fallback_used: bool,
    tokens: tuple[str, ...],
    debug_info: dict[str, Any],
    generation_time_ms: float = 0.0,
) -> Any:
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
                generation_time_ms=generation_time_ms,
            )
        except TypeError:
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
                pass

    return _FallbackSurfaceResult(
        text=text,
        lang_code=lang_code,
        construction_id=construction_id,
        renderer_backend=renderer_backend,
        fallback_used=fallback_used,
        tokens=tokens,
        debug_info=debug_info,
        generation_time_ms=generation_time_ms,
    )


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


class ConstructionRealizer:
    """
    Canonical runtime dispatcher for renderer backends.

    Public contract:
        ConstructionPlan -> SurfaceResult

    Dispatch policy:
        1. GF, when supported and healthy
        2. family backend, when available
        3. safe_mode, when fallback is allowed

    The dispatcher itself does not reinterpret the construction. It only selects
    which backend is allowed to realize the already-chosen ConstructionPlan.
    """

    def __init__(
        self,
        *,
        gf_realizer: "RealizerPort | None" = None,
        family_realizer: "RealizerPort | None" = None,
        safe_mode_realizer: "RealizerPort | None" = None,
        default_allow_fallback: bool = True,
        dispatch_order: Sequence[str] = _CANONICAL_BACKEND_ORDER,
    ) -> None:
        self._realizers: dict[str, Any] = {
            "gf": gf_realizer,
            "family": family_realizer,
            "safe_mode": safe_mode_realizer,
        }
        self.default_allow_fallback = bool(default_allow_fallback)

        normalized_order: list[str] = []
        for item in dispatch_order:
            normalized = _normalize_backend_name(item)
            if normalized in _CANONICAL_BACKEND_ORDER and normalized not in normalized_order:
                normalized_order.append(normalized)

        for canonical in _CANONICAL_BACKEND_ORDER:
            if canonical not in normalized_order:
                normalized_order.append(canonical)

        self.dispatch_order: tuple[str, ...] = tuple(normalized_order)

    @property
    def backend_name(self) -> str:
        return "dispatcher"

    def supports(self, construction_id: str, lang_code: str) -> bool:
        return self.get_support_status(construction_id, lang_code) != "unsupported"

    def get_support_status(
        self,
        construction_id: str,
        lang_code: str,
    ) -> "RealizerSupportStatus":
        seen_partial = False
        seen_fallback_only = False

        for backend_name in self.dispatch_order:
            realizer = self._realizers.get(backend_name)
            if realizer is None:
                continue

            status = self._get_backend_support_status(
                backend_name=backend_name,
                realizer=realizer,
                construction_id=construction_id,
                lang_code=lang_code,
            )

            if status == "full":
                return "full"
            if status == "partial":
                seen_partial = True
            elif status == "fallback_only":
                seen_fallback_only = True

        if seen_partial:
            return "partial"
        if seen_fallback_only:
            return "fallback_only"
        return "unsupported"

    async def realize(self, construction_plan: "ConstructionPlan") -> "SurfaceResult":
        plan = self._validate_plan(construction_plan)
        construction_id = str(_get_value(plan, "construction_id")).strip()
        lang_code = str(_get_value(plan, "lang_code")).strip()

        forced_backend = self._resolve_forced_backend(plan)
        allow_fallback = self._resolve_allow_fallback(plan)

        call_order = self._resolve_call_order(
            construction_id=construction_id,
            lang_code=lang_code,
            forced_backend=forced_backend,
            allow_fallback=allow_fallback,
        )

        if not call_order:
            raise RealizationError(
                f"No realization backend is configured for construction "
                f"'{construction_id}' and language '{lang_code}'."
            )

        backend_trace: list[dict[str, Any]] = []
        attempted_backends: list[str] = []
        failures: list[dict[str, str]] = []

        for backend_name in call_order:
            realizer = self._realizers.get(backend_name)
            if realizer is None:
                backend_trace.append(
                    {
                        "backend": backend_name,
                        "event": "skipped",
                        "reason": "not_configured",
                    }
                )
                continue

            support_status = self._get_backend_support_status(
                backend_name=backend_name,
                realizer=realizer,
                construction_id=construction_id,
                lang_code=lang_code,
            )

            if support_status not in _ATTEMPTABLE_STATUSES:
                backend_trace.append(
                    {
                        "backend": backend_name,
                        "event": "skipped",
                        "reason": "unsupported",
                        "capability_tier": support_status,
                    }
                )
                continue

            attempted_backends.append(backend_name)

            try:
                raw_result = await _maybe_await(realizer.realize(plan))
            except DomainError as exc:
                failures.append({"backend": backend_name, "error": str(exc)})
                backend_trace.append(
                    {
                        "backend": backend_name,
                        "event": "failed",
                        "capability_tier": support_status,
                        "error": str(exc),
                    }
                )

                if forced_backend is not None:
                    raise

                continue
            except Exception as exc:
                failures.append({"backend": backend_name, "error": str(exc)})
                backend_trace.append(
                    {
                        "backend": backend_name,
                        "event": "failed",
                        "capability_tier": support_status,
                        "error": str(exc),
                    }
                )

                if forced_backend is not None:
                    raise RealizationError(
                        f"Forced backend '{backend_name}' failed for construction "
                        f"'{construction_id}' and language '{lang_code}': {exc}"
                    ) from exc

                continue

            backend_trace.append(
                {
                    "backend": backend_name,
                    "event": "selected",
                    "capability_tier": support_status,
                }
            )

            dispatch_fallback_used = (
                len(attempted_backends) > 1
                or (backend_name == "safe_mode" and forced_backend is None)
            )

            return self._normalize_result(
                raw_result,
                plan,
                selected_backend=backend_name,
                capability_tier=support_status,
                attempted_backends=attempted_backends,
                backend_trace=backend_trace,
                forced_backend=forced_backend,
                allow_fallback=allow_fallback,
                dispatch_fallback_used=dispatch_fallback_used,
            )

        detail = "; ".join(
            f"{item['backend']}: {item['error']}"
            for item in failures
            if item.get("backend") and item.get("error")
        ) or "no backend produced a result"

        raise RealizationError(
            f"Could not realize construction '{construction_id}' for language "
            f"'{lang_code}'. {detail}"
        )

    __call__ = realize

    def _validate_plan(self, construction_plan: Any) -> Any:
        if construction_plan is None:
            raise RealizationError("construction_plan must not be None")

        construction_id = _get_value(construction_plan, "construction_id")
        lang_code = _get_value(construction_plan, "lang_code")
        slot_map = _get_value(construction_plan, "slot_map")

        if not _is_non_empty_string(construction_id):
            raise RealizationError("construction_plan.construction_id must be a non-empty string")
        if not _is_non_empty_string(lang_code):
            raise RealizationError("construction_plan.lang_code must be a non-empty string")
        if slot_map is None:
            raise RealizationError("construction_plan.slot_map must be present")

        return construction_plan

    def _resolve_generation_options(self, construction_plan: Any) -> dict[str, Any]:
        plan_options = _as_plain_dict(_get_value(construction_plan, "generation_options", {}))
        metadata = _as_plain_dict(_get_value(construction_plan, "metadata", {}))
        metadata_options = _as_plain_dict(metadata.get("generation_options", {}))

        merged: dict[str, Any] = {}
        merged.update(metadata_options)
        merged.update(plan_options)
        return merged

    def _resolve_forced_backend(self, construction_plan: Any) -> str | None:
        options = self._resolve_generation_options(construction_plan)

        for key in ("force_backend", "renderer_backend", "backend"):
            normalized = _normalize_backend_name(options.get(key))
            if normalized in _CANONICAL_BACKEND_ORDER:
                return normalized

        return None

    def _resolve_allow_fallback(self, construction_plan: Any) -> bool:
        options = self._resolve_generation_options(construction_plan)
        return _truthy(options.get("allow_fallback"), default=self.default_allow_fallback)

    def _resolve_call_order(
        self,
        *,
        construction_id: str,
        lang_code: str,
        forced_backend: str | None,
        allow_fallback: bool,
    ) -> tuple[str, ...]:
        if forced_backend is not None:
            realizer = self._realizers.get(forced_backend)
            if realizer is None:
                raise RealizationError(f"Forced backend '{forced_backend}' is not configured")

            status = self._get_backend_support_status(
                backend_name=forced_backend,
                realizer=realizer,
                construction_id=construction_id,
                lang_code=lang_code,
            )
            if status not in _ATTEMPTABLE_STATUSES:
                raise RealizationError(
                    f"Forced backend '{forced_backend}' does not support construction "
                    f"'{construction_id}' for language '{lang_code}'"
                )
            return (forced_backend,)

        ordered: list[str] = []

        for backend_name in self.dispatch_order:
            if backend_name == "safe_mode" and not allow_fallback:
                continue

            realizer = self._realizers.get(backend_name)
            if realizer is None:
                continue

            status = self._get_backend_support_status(
                backend_name=backend_name,
                realizer=realizer,
                construction_id=construction_id,
                lang_code=lang_code,
            )

            if status in _ATTEMPTABLE_STATUSES:
                ordered.append(backend_name)

        return tuple(ordered)

    def _get_backend_support_status(
        self,
        *,
        backend_name: str,
        realizer: Any,
        construction_id: str,
        lang_code: str,
    ) -> str:
        getter = getattr(realizer, "get_support_status", None)
        if callable(getter):
            try:
                return _normalize_support_status(getter(construction_id, lang_code))
            except Exception:
                return "unsupported"

        supports = getattr(realizer, "supports", None)
        if callable(supports):
            try:
                return "full" if bool(supports(construction_id, lang_code)) else "unsupported"
            except Exception:
                return "unsupported"

        # Conservative defaults for migration-era adapters:
        if backend_name == "safe_mode":
            return "fallback_only"
        return "partial"

    def _normalize_result(
        self,
        raw_result: Any,
        construction_plan: Any,
        *,
        selected_backend: str,
        capability_tier: str,
        attempted_backends: list[str],
        backend_trace: list[dict[str, Any]],
        forced_backend: str | None,
        allow_fallback: bool,
        dispatch_fallback_used: bool,
    ) -> Any:
        if raw_result is None:
            raise RealizationError(
                f"Backend '{selected_backend}' returned None instead of a surface result"
            )

        construction_id = str(_get_value(construction_plan, "construction_id")).strip()
        plan_lang_code = str(_get_value(construction_plan, "lang_code")).strip().lower()

        text = _get_value(raw_result, "text")
        if not _is_non_empty_string(text):
            if isinstance(raw_result, str) and raw_result.strip():
                text = raw_result.strip()
            else:
                raise RealizationError(
                    f"Backend '{selected_backend}' returned no usable text"
                )

        lang_code = _get_value(raw_result, "lang_code", plan_lang_code)
        if not _is_non_empty_string(lang_code):
            lang_code = plan_lang_code
        lang_code = str(lang_code).strip().lower()

        debug_info = _as_plain_dict(_get_value(raw_result, "debug_info", {}))
        child_fallback = bool(
            _get_value(raw_result, "fallback_used", debug_info.get("fallback_used", False))
        )
        fallback_used = bool(child_fallback or dispatch_fallback_used)

        tokens = _normalize_tokens(_get_value(raw_result, "tokens"))
        if not tokens:
            tokens = tuple(part for part in str(text).split() if part)

        generation_time_ms = _get_value(raw_result, "generation_time_ms", 0.0)
        try:
            generation_time_ms = float(generation_time_ms or 0.0)
        except Exception:
            generation_time_ms = 0.0

        debug_info["construction_id"] = construction_id
        debug_info["lang_code"] = lang_code
        debug_info["renderer_backend"] = selected_backend
        debug_info["selected_backend"] = selected_backend
        debug_info["attempted_backends"] = list(attempted_backends)
        debug_info["fallback_used"] = fallback_used
        debug_info.setdefault("capability_tier", capability_tier)
        debug_info["backend_trace"] = list(backend_trace)
        debug_info.setdefault(
            "dispatch_policy",
            {
                "allow_fallback": allow_fallback,
                "forced_backend": forced_backend,
            },
        )

        return _build_result_object(
            text=str(text).strip(),
            lang_code=lang_code,
            construction_id=construction_id,
            renderer_backend=selected_backend,
            fallback_used=fallback_used,
            tokens=tokens,
            debug_info=debug_info,
            generation_time_ms=generation_time_ms,
        )


__all__ = [
    "ConstructionRealizer",
    "RealizationError",
]