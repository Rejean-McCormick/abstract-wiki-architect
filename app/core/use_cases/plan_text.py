# app/core/use_cases/plan_text.py
from __future__ import annotations

import inspect
import re
from collections.abc import Iterable, Mapping, Sequence
from typing import Any, Optional, Protocol, runtime_checkable

import structlog

from app.core.domain.exceptions import DomainError, InvalidFrameError
from app.core.domain.planning.planned_sentence import PlannedSentence
from app.shared.observability import get_tracer

try:
    # Optional during migration; keep this use case resilient even if shared
    # lexicon runtime is unavailable in isolated unit tests.
    from app.shared.lexicon import lexicon
except Exception:  # pragma: no cover - defensive import fallback
    lexicon = None  # type: ignore[assignment]


logger = structlog.get_logger()
tracer = get_tracer(__name__)

_BIOISH_FRAME_TYPES = {
    "bio",
    "biography",
    "entity.person",
    "entity_person",
    "person",
    "entity.person.v1",
    "entity.person.v2",
}

_CANONICAL_CONSTRUCTION_ID_RE = re.compile(r"^[a-z0-9_]+$")


@runtime_checkable
class _PlannerLike(Protocol):
    """
    Minimal planner contract used by this use case.

    The canonical port will live in `app.core.ports.planner_port`, but this
    local protocol keeps the use case compile-safe during migration and makes
    unit testing straightforward.

    Supported entrypoint shapes:

        async def plan(*, lang_code: str, frame: Any) -> PlannedSentence | Sequence[PlannedSentence]
        async def plan(lang_code: str, frame: Any) -> PlannedSentence | Sequence[PlannedSentence]

    During migration, `plan_text`, or even `execute`, are also accepted as
    fallback method names if they expose the same semantics.
    """

    async def plan(self, *, lang_code: str, frame: Any) -> Any:
        ...


class PlanText:
    """
    Use Case: planner-stage runtime entrypoint.

    Responsibilities:
    1. Validate a normalized semantic frame at the application boundary.
    2. Normalize the language code conservatively.
    3. Invoke the planner port / adapter.
    4. Normalize planner output into a stable `list[PlannedSentence]`.
    5. Validate planner output so later stages receive a clean contract.

    Notes:
    - This use case does NOT perform lexical resolution.
    - This use case does NOT realize text.
    - Planner output is authoritative for sentence intent.
    """

    def __init__(self, planner: _PlannerLike):
        self.planner = planner

    async def execute(self, lang_code: str, frame: Any) -> list[PlannedSentence]:
        """
        Produce one or more backend-neutral sentence plans from a frame.

        Args:
            lang_code:
                Requested language code. ISO-2 / ISO-3 inputs are tolerated and
                normalized conservatively where possible.
            frame:
                A normalized semantic frame or compatible legacy frame object.

        Returns:
            A non-empty list of `PlannedSentence` objects.

        Raises:
            InvalidFrameError:
                If the input frame is structurally invalid.
            DomainError:
                If the planner cannot be invoked, returns an invalid result, or
                any unexpected runtime failure occurs.
        """
        normalized_lang = self._normalize_lang_code(lang_code)
        frame_type = self._frame_type(frame) or "unknown"

        with tracer.start_as_current_span("use_case.plan_text") as span:
            span.set_attribute("app.lang_code", normalized_lang)
            span.set_attribute("app.frame_type", frame_type)

            logger.info(
                "planning_started",
                lang=normalized_lang,
                frame_type=frame_type,
            )

            try:
                self._validate_frame(frame)

                raw_plan = await self._invoke_planner(
                    planner=self.planner,
                    lang_code=normalized_lang,
                    frame=frame,
                )

                planned_sentences = self._normalize_plan_result(raw_plan)
                self._validate_planned_sentences(planned_sentences)

                span.set_attribute("app.plan_count", len(planned_sentences))
                if planned_sentences:
                    span.set_attribute(
                        "app.first_construction_id",
                        str(planned_sentences[0].construction_id),
                    )

                logger.info(
                    "planning_success",
                    lang=normalized_lang,
                    frame_type=frame_type,
                    plan_count=len(planned_sentences),
                    construction_ids=[p.construction_id for p in planned_sentences],
                )
                return planned_sentences

            except DomainError:
                raise
            except Exception as exc:
                logger.error("planning_failed", error=str(exc), exc_info=True)
                raise DomainError(f"Unexpected planning failure: {exc}") from exc

    async def execute_one(self, lang_code: str, frame: Any) -> PlannedSentence:
        """
        Convenience wrapper for callers that require exactly one sentence plan.

        This is useful during migration where some call sites still assume a
        single-sentence generation path.

        Raises:
            DomainError:
                If zero or multiple planned sentences are produced.
        """
        planned = await self.execute(lang_code=lang_code, frame=frame)

        if len(planned) != 1:
            raise DomainError(
                f"Expected exactly one planned sentence, but planner produced {len(planned)}."
            )

        return planned[0]

    # ------------------------------------------------------------------
    # Input validation
    # ------------------------------------------------------------------

    def _validate_frame(self, frame: Any) -> None:
        if frame is None:
            raise InvalidFrameError("Frame is required.")

        frame_type = self._frame_type(frame)
        if not frame_type:
            raise InvalidFrameError("Frame must have a non-empty 'frame_type'.")

        # Keep validation strict enough to fail fast, but not so strict that it
        # rejects legitimate future frame families.
        if frame_type in _BIOISH_FRAME_TYPES:
            subject = self._get_member(frame, "subject")
            name = self._extract_name(subject) or self._get_member(frame, "name")
            if not name:
                raise InvalidFrameError(
                    "Bio/person frames require a subject with a non-empty 'name'."
                )

    # ------------------------------------------------------------------
    # Planner invocation
    # ------------------------------------------------------------------

    async def _invoke_planner(self, *, planner: Any, lang_code: str, frame: Any) -> Any:
        """
        Invoke a planner adapter safely without depending on one temporary
        method name during migration.

        Accepted method names, in order:
        - plan
        - plan_text
        - execute
        """
        entrypoint = None
        entrypoint_name = None

        for candidate in ("plan", "plan_text", "execute"):
            method = getattr(planner, candidate, None)
            if callable(method):
                entrypoint = method
                entrypoint_name = candidate
                break

        if entrypoint is None:
            raise DomainError(
                "Planner adapter does not expose a supported planning entrypoint."
            )

        result = self._call_planner_entrypoint(
            entrypoint,
            lang_code=lang_code,
            frame=frame,
        )

        if inspect.isawaitable(result):
            result = await result

        logger.debug(
            "planner_invoked",
            planner_method=entrypoint_name,
            lang_code=lang_code,
            frame_type=self._frame_type(frame),
        )
        return result

    def _call_planner_entrypoint(self, method: Any, *, lang_code: str, frame: Any) -> Any:
        """
        Call the planner in a signature-aware way.

        Preferred contract:
            method(*, lang_code=..., frame=...)

        Also accepts:
            method(lang_code, frame)

        This avoids swallowing internal `TypeError`s from the planner body.
        """
        try:
            sig = inspect.signature(method)
        except (TypeError, ValueError):
            # Fallback for unusual callables; prefer canonical kwargs first.
            return method(lang_code=lang_code, frame=frame)

        params = list(sig.parameters.values())
        param_names = {p.name for p in params}
        accepts_varkw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params)

        if accepts_varkw or {"lang_code", "frame"}.issubset(param_names):
            return method(lang_code=lang_code, frame=frame)

        # Bound method signatures do not include `self`.
        positional_params = [
            p
            for p in params
            if p.kind in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            )
        ]
        if len(positional_params) >= 2:
            return method(lang_code, frame)

        raise DomainError(
            "Planner entrypoint must accept `lang_code` and `frame`."
        )

    # ------------------------------------------------------------------
    # Planner output normalization
    # ------------------------------------------------------------------

    def _normalize_plan_result(self, raw_plan: Any) -> list[PlannedSentence]:
        """
        Normalize planner output into a non-empty `list[PlannedSentence]`.

        Supported outputs:
        - a single `PlannedSentence`
        - an equivalent mapping / model / dataclass-like object
        - an iterable of the above
        """
        if raw_plan is None:
            raise DomainError("Planner returned no result.")

        if self._is_single_plan_candidate(raw_plan):
            return [self._coerce_planned_sentence(raw_plan)]

        if isinstance(raw_plan, (str, bytes)):
            raise DomainError("Planner returned an invalid string-like result.")

        if isinstance(raw_plan, Sequence):
            items = list(raw_plan)
        elif isinstance(raw_plan, Iterable):
            items = list(raw_plan)
        else:
            raise DomainError(
                f"Planner returned unsupported result type: {type(raw_plan).__name__}."
            )

        if not items:
            raise DomainError("Planner produced no sentence plans.")

        return [self._coerce_planned_sentence(item) for item in items]

    def _is_single_plan_candidate(self, value: Any) -> bool:
        if isinstance(value, PlannedSentence):
            return True

        if isinstance(value, Mapping):
            return "construction_id" in value and "frame" in value

        return hasattr(value, "construction_id") and hasattr(value, "frame")

    def _coerce_planned_sentence(self, value: Any) -> PlannedSentence:
        if isinstance(value, PlannedSentence):
            return value

        payload = self._extract_payload(value)

        construction_id = payload.get("construction_id")
        if not isinstance(construction_id, str) or not construction_id.strip():
            raise DomainError("Planner returned a sentence plan without a valid construction_id.")

        if "frame" not in payload:
            raise DomainError("Planner returned a sentence plan without a frame.")

        try:
            planned_sig = inspect.signature(PlannedSentence)
            allowed = {
                name
                for name, param in planned_sig.parameters.items()
                if name != "self"
                and param.kind
                in (
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    inspect.Parameter.KEYWORD_ONLY,
                )
            }
        except (TypeError, ValueError):
            allowed = {
                "frame",
                "construction_id",
                "topic_entity_id",
                "focus_role",
                "metadata",
            }

        kwargs: dict[str, Any] = {}

        for key in allowed:
            if key not in payload:
                continue
            if key == "metadata":
                meta = payload.get("metadata")
                kwargs[key] = dict(meta) if isinstance(meta, Mapping) else {}
            else:
                kwargs[key] = payload.get(key)

        # Ensure the minimum contract survives even if the runtime class grows.
        kwargs.setdefault("frame", payload.get("frame"))
        kwargs.setdefault("construction_id", construction_id)

        if "topic_entity_id" in allowed:
            kwargs.setdefault("topic_entity_id", self._optional_str(payload.get("topic_entity_id")))
        if "focus_role" in allowed:
            kwargs.setdefault("focus_role", self._optional_str(payload.get("focus_role")))
        if "metadata" in allowed:
            kwargs.setdefault(
                "metadata",
                dict(payload.get("metadata")) if isinstance(payload.get("metadata"), Mapping) else {},
            )

        try:
            return PlannedSentence(**kwargs)
        except TypeError as exc:
            raise DomainError(
                f"Planner returned a sentence plan incompatible with PlannedSentence: {exc}"
            ) from exc

    def _extract_payload(self, value: Any) -> dict[str, Any]:
        """
        Convert a mapping / pydantic model / dataclass-like object into a dict.
        """
        if isinstance(value, Mapping):
            return dict(value)

        if hasattr(value, "model_dump") and callable(value.model_dump):
            dumped = value.model_dump()
            if isinstance(dumped, Mapping):
                return dict(dumped)

        if hasattr(value, "__dict__"):
            raw = {
                key: val
                for key, val in vars(value).items()
                if not key.startswith("_")
            }
            if raw:
                return raw

        # Last-resort attribute extraction for lightweight objects.
        keys = ("frame", "construction_id", "topic_entity_id", "focus_role", "metadata")
        payload = {key: getattr(value, key) for key in keys if hasattr(value, key)}
        if payload:
            return payload

        raise DomainError(
            f"Unable to interpret planner output item of type {type(value).__name__}."
        )

    def _validate_planned_sentences(self, planned_sentences: Sequence[PlannedSentence]) -> None:
        if not planned_sentences:
            raise DomainError("Planner produced no sentence plans.")

        for index, planned in enumerate(planned_sentences):
            construction_id = getattr(planned, "construction_id", None)
            if not isinstance(construction_id, str) or not construction_id.strip():
                raise DomainError(
                    f"PlannedSentence at index {index} is missing a valid construction_id."
                )

            if not _CANONICAL_CONSTRUCTION_ID_RE.fullmatch(construction_id):
                raise DomainError(
                    f"PlannedSentence at index {index} has non-canonical construction_id "
                    f"{construction_id!r}."
                )

            if getattr(planned, "frame", None) is None:
                raise DomainError(
                    f"PlannedSentence at index {index} is missing its source frame."
                )

            metadata = getattr(planned, "metadata", {})
            if metadata is not None and not isinstance(metadata, Mapping):
                raise DomainError(
                    f"PlannedSentence at index {index} has invalid metadata; expected a mapping."
                )

    # ------------------------------------------------------------------
    # Lightweight normalization / extraction helpers
    # ------------------------------------------------------------------

    def _normalize_lang_code(self, lang_code: str) -> str:
        raw = (lang_code or "").strip()
        if not raw:
            raise DomainError("Language code is required.")

        lowered = raw.lower()
        if lexicon is not None and hasattr(lexicon, "normalize_code"):
            try:
                normalized = lexicon.normalize_code(lowered)
                if isinstance(normalized, str) and normalized.strip():
                    return normalized.strip().lower()
            except Exception:
                # Keep planning resilient; later stages may perform stricter checks.
                logger.warning("lang_code_normalization_failed", input_code=raw)

        # Conservative fallback:
        # - preserve 2-letter codes
        # - trim longer codes to 2 chars only as a migration fallback
        return lowered if len(lowered) <= 2 else lowered[:2]

    def _frame_type(self, frame: Any) -> str:
        value = self._get_member(frame, "frame_type")
        return value.strip().lower() if isinstance(value, str) else ""

    def _get_member(self, obj: Any, key: str) -> Any:
        if obj is None:
            return None
        if isinstance(obj, Mapping):
            return obj.get(key)
        return getattr(obj, key, None)

    def _extract_name(self, subject: Any) -> Optional[str]:
        value = self._get_member(subject, "name")
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None

    def _optional_str(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return str(value)