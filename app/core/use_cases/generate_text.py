# app/core/use_cases/generate_text.py
from __future__ import annotations

import inspect
import time
from typing import Any, Optional

import structlog

from app.core.domain.exceptions import DomainError, InvalidFrameError
from app.core.domain.models import Frame, Sentence
from app.core.ports.grammar_engine import IGrammarEngine
from app.core.ports.llm_port import ILanguageModel
from app.shared.observability import get_tracer

logger = structlog.get_logger()
tracer = get_tracer(__name__)


class GenerateText:
    """
    Public application use case for single-sentence generation.

    Migration behavior:
    - Preferred path: planner-first runtime
        frame -> planner -> lexical resolution -> realizer -> Sentence
    - Compatibility path: legacy grammar engine
        frame -> engine.generate(...) -> Sentence

    Notes:
    - The planner-first path is attempted only when the required runtime
      components are injected.
    - Legacy direct-engine generation is retained as an explicit fallback
      during migration and is always recorded in debug_info when used.
    - This class intentionally remains tolerant of evolving planner/realizer
      contracts so it can bridge the migration safely.
    """

    def __init__(
        self,
        engine: Optional[IGrammarEngine] = None,
        llm: Optional[ILanguageModel] = None,
        *,
        planner: Any | None = None,
        lexical_resolver: Any | None = None,
        realizer: Any | None = None,
        allow_legacy_engine_fallback: bool = True,
    ) -> None:
        # Legacy compatibility dependency
        self.engine = engine

        # Optional post-processing dependency (not used by default)
        self.llm = llm

        # New runtime dependencies
        self.planner = planner
        self.lexical_resolver = lexical_resolver
        self.realizer = realizer

        # Migration control
        self.allow_legacy_engine_fallback = allow_legacy_engine_fallback

    async def execute(self, lang_code: str, frame: Frame) -> Sentence:
        """
        Generate a single Sentence from a semantic Frame.

        Args:
            lang_code:
                Target language code.
            frame:
                Semantic/domain frame.

        Returns:
            Sentence:
                Compatibility wrapper over the final surface result.

        Raises:
            InvalidFrameError:
                When the input frame is structurally invalid.
            DomainError:
                When generation fails or the use case is misconfigured.
        """
        started = time.perf_counter()

        with tracer.start_as_current_span("use_case.generate_text") as span:
            frame_type = str(getattr(frame, "frame_type", "unknown") or "unknown")

            span.set_attribute("app.lang_code", lang_code or "")
            span.set_attribute("app.frame_type", frame_type)

            logger.info(
                "generation_started",
                lang=lang_code,
                frame_type=frame_type,
                planner_runtime_configured=self._planner_runtime_available(),
                legacy_engine_configured=self.engine is not None,
            )

            try:
                self._validate_lang_code(lang_code)
                self._validate_frame(frame)

                sentence: Sentence
                runtime_path: str

                if self._planner_runtime_available():
                    try:
                        sentence = await self._generate_via_planner_runtime(
                            lang_code=lang_code,
                            frame=frame,
                        )
                        runtime_path = "planner_first"
                    except InvalidFrameError:
                        raise
                    except Exception as planner_exc:
                        if not self._can_fallback_to_legacy_engine():
                            raise

                        logger.warning(
                            "planner_runtime_failed_falling_back",
                            lang=lang_code,
                            frame_type=frame_type,
                            error=str(planner_exc),
                            planner=self._component_name(self.planner),
                            lexical_resolver=self._component_name(self.lexical_resolver),
                            realizer=self._component_name(self.realizer),
                        )

                        sentence = await self._generate_via_legacy_engine(
                            lang_code=lang_code,
                            frame=frame,
                            fallback_reason=str(planner_exc),
                        )
                        runtime_path = "legacy_engine_fallback"
                else:
                    if self.engine is None:
                        raise DomainError(
                            "GenerateText is not configured with either "
                            "a planner-first runtime or a legacy grammar engine."
                        )

                    sentence = await self._generate_via_legacy_engine(
                        lang_code=lang_code,
                        frame=frame,
                        fallback_reason=None,
                    )
                    runtime_path = "legacy_engine"

                sentence = self._finalize_sentence(
                    sentence=sentence,
                    lang_code=lang_code,
                    elapsed_ms=(time.perf_counter() - started) * 1000.0,
                    runtime_path=runtime_path,
                )

                span.set_attribute("app.runtime_path", runtime_path)
                span.set_attribute("app.generated_length", len(sentence.text))
                span.set_attribute(
                    "app.fallback_used",
                    bool((sentence.debug_info or {}).get("fallback_used", False)),
                )

                construction_id = (sentence.debug_info or {}).get("construction_id")
                renderer_backend = (sentence.debug_info or {}).get("renderer_backend")

                if construction_id:
                    span.set_attribute("app.construction_id", str(construction_id))
                if renderer_backend:
                    span.set_attribute("app.renderer_backend", str(renderer_backend))

                logger.info(
                    "generation_success",
                    lang=sentence.lang_code,
                    runtime_path=runtime_path,
                    text_preview=sentence.text[:80],
                    construction_id=construction_id,
                    renderer_backend=renderer_backend,
                    fallback_used=bool(
                        (sentence.debug_info or {}).get("fallback_used", False)
                    ),
                )

                return sentence

            except DomainError:
                raise
            except Exception as exc:
                logger.error(
                    "generation_failed",
                    lang=lang_code,
                    frame_type=frame_type,
                    error=str(exc),
                    exc_info=True,
                )
                raise DomainError(f"Unexpected generation failure: {str(exc)}") from exc

    async def _generate_via_planner_runtime(self, *, lang_code: str, frame: Frame) -> Sentence:
        """
        Run the preferred planner-first runtime.

        This method is intentionally tolerant of evolving intermediate runtime
        contracts during migration:
        - planner output may be a single object or a sequence,
        - lexical resolver is optional,
        - realizer is authoritative for the final surface result.
        """
        planned = await self._call_planner(lang_code=lang_code, frame=frame)
        runtime_payload = planned

        if self.lexical_resolver is not None:
            runtime_payload = await self._call_lexical_resolver(
                payload=runtime_payload,
                lang_code=lang_code,
                frame=frame,
            )

        realized = await self._call_realizer(
            payload=runtime_payload,
            lang_code=lang_code,
            frame=frame,
        )

        debug_info = {
            "runtime_path": "planner_first",
            "fallback_used": False,
            "planner": self._component_name(self.planner),
            "lexical_resolver": self._component_name(self.lexical_resolver),
            "realizer": self._component_name(self.realizer),
        }

        return self._coerce_to_sentence(
            value=realized,
            lang_code=lang_code,
            default_debug_info=debug_info,
        )

    async def _generate_via_legacy_engine(
        self,
        *,
        lang_code: str,
        frame: Frame,
        fallback_reason: str | None,
    ) -> Sentence:
        """
        Run the legacy direct frame-to-engine path.

        This path remains available only as an explicit migration compatibility
        route and must annotate fallback information in debug_info.
        """
        if self.engine is None:
            raise DomainError("Legacy grammar engine fallback is not configured.")

        result = await self.engine.generate(lang_code, frame)

        debug_info = {
            "runtime_path": "legacy_engine_fallback" if fallback_reason else "legacy_engine",
            "fallback_used": bool(fallback_reason),
            "fallback_reason": fallback_reason,
            "legacy_engine": self._component_name(self.engine),
            "planner_runtime_configured": self._planner_runtime_available(),
        }

        return self._coerce_to_sentence(
            value=result,
            lang_code=lang_code,
            default_debug_info=debug_info,
        )

    async def _call_planner(self, *, lang_code: str, frame: Frame) -> Any:
        if self.planner is None:
            raise DomainError("Planner runtime is not configured.")

        attempts = [
            (((frame,),), {"lang_code": lang_code}),   # planner may accept a sequence of frames
            (((frame,),), {"lang_code": lang_code, "domain": "auto"}),
            ((frame,), {"lang_code": lang_code}),      # planner may accept a single frame
            (((frame,),), {}),
            ((frame,), {}),
        ]

        result = await self._call_method_attempts(self.planner, "plan", attempts)
        return self._normalize_single_sentence_payload(result, stage="planner")

    async def _call_lexical_resolver(
        self,
        *,
        payload: Any,
        lang_code: str,
        frame: Frame,
    ) -> Any:
        resolver = self.lexical_resolver
        if resolver is None:
            return payload

        attempts = [
            ((payload,), {"lang_code": lang_code, "frame": frame}),
            ((payload,), {"lang_code": lang_code}),
            ((payload,), {}),
        ]

        return await self._call_method_attempts(resolver, "resolve", attempts)

    async def _call_realizer(
        self,
        *,
        payload: Any,
        lang_code: str,
        frame: Frame,
    ) -> Any:
        if self.realizer is None:
            raise DomainError("Planner runtime is missing a realizer.")

        attempts = [
            ((payload,), {"lang_code": lang_code, "frame": frame}),
            ((payload,), {"lang_code": lang_code}),
            ((payload,), {}),
        ]

        return await self._call_method_attempts(self.realizer, "realize", attempts)

    async def _call_method_attempts(
        self,
        target: Any,
        method_name: str,
        attempts: list[tuple[tuple[Any, ...], dict[str, Any]]],
    ) -> Any:
        """
        Attempt a method call across a small set of migration-safe signatures.

        This keeps GenerateText stable while the planner/lexical/realizer port
        contracts are being introduced and adapters are catching up.
        """
        method = getattr(target, method_name, None)
        if method is None:
            raise DomainError(
                f"{self._component_name(target)} does not implement '{method_name}()'."
            )

        last_type_error: TypeError | None = None

        for args, kwargs in attempts:
            try:
                value = method(*args, **kwargs)
                if inspect.isawaitable(value):
                    value = await value
                return value
            except TypeError as exc:
                last_type_error = exc
                continue

        raise DomainError(
            f"{self._component_name(target)}.{method_name}() could not be called "
            f"with any supported migration signature."
        ) from last_type_error

    def _normalize_single_sentence_payload(self, value: Any, *, stage: str) -> Any:
        """
        Normalize planner-like outputs to the single-sentence runtime payload
        that GenerateText currently supports.
        """
        if value is None:
            raise DomainError(f"{stage.capitalize()} returned no result.")

        if isinstance(value, (str, bytes, bytearray, dict, Sentence)):
            return value

        if isinstance(value, (list, tuple)):
            if not value:
                raise DomainError(f"{stage.capitalize()} returned an empty sequence.")
            return value[0]

        return value

    def _coerce_to_sentence(
        self,
        *,
        value: Any,
        lang_code: str,
        default_debug_info: dict[str, Any],
    ) -> Sentence:
        """
        Convert a planner/realizer/engine result into the compatibility Sentence type.
        """
        if isinstance(value, Sentence):
            return Sentence(
                text=value.text,
                lang_code=value.lang_code or lang_code,
                debug_info=self._merge_debug_info(value.debug_info, default_debug_info),
                generation_time_ms=float(getattr(value, "generation_time_ms", 0.0) or 0.0),
            )

        if isinstance(value, str):
            return Sentence(
                text=value,
                lang_code=lang_code,
                debug_info=dict(default_debug_info),
                generation_time_ms=0.0,
            )

        if isinstance(value, dict):
            text = value.get("text")
            if text is None:
                raise DomainError("Generation result dict is missing required field 'text'.")

            return Sentence(
                text=str(text),
                lang_code=str(value.get("lang_code") or lang_code),
                debug_info=self._merge_debug_info(value.get("debug_info"), default_debug_info),
                generation_time_ms=float(value.get("generation_time_ms") or 0.0),
            )

        text = getattr(value, "text", None)
        if text is None:
            raise DomainError(
                f"Cannot map result of type '{type(value).__name__}' into Sentence: "
                "missing 'text'."
            )

        debug_info = getattr(value, "debug_info", None)
        result_lang = getattr(value, "lang_code", None) or getattr(value, "language", None)

        # SurfaceResult-like objects often expose useful runtime metadata as attributes.
        extra_debug: dict[str, Any] = dict(default_debug_info)
        for key in (
            "construction_id",
            "renderer_backend",
            "fallback_used",
            "tokens",
            "selected_backend",
        ):
            attr = getattr(value, key, None)
            if attr is not None:
                extra_debug.setdefault(key, attr)

        return Sentence(
            text=str(text),
            lang_code=str(result_lang or lang_code),
            debug_info=self._merge_debug_info(debug_info, extra_debug),
            generation_time_ms=float(
                getattr(value, "generation_time_ms", 0.0) or 0.0
            ),
        )

    def _finalize_sentence(
        self,
        *,
        sentence: Sentence,
        lang_code: str,
        elapsed_ms: float,
        runtime_path: str,
    ) -> Sentence:
        """
        Final cleanup to guarantee a stable Sentence shape.
        """
        text = str(sentence.text or "").strip()
        debug_info = dict(sentence.debug_info or {})
        debug_info.setdefault("runtime_path", runtime_path)
        debug_info.setdefault("fallback_used", False)

        generation_time_ms = float(sentence.generation_time_ms or 0.0)
        if generation_time_ms <= 0.0:
            generation_time_ms = elapsed_ms

        return Sentence(
            text=text,
            lang_code=str(sentence.lang_code or lang_code),
            debug_info=debug_info,
            generation_time_ms=generation_time_ms,
        )

    def _validate_lang_code(self, lang_code: str) -> None:
        if not isinstance(lang_code, str) or not lang_code.strip():
            raise DomainError("lang_code must be a non-empty string.")

    def _validate_frame(self, frame: Frame) -> None:
        """
        Enforce semantic preconditions before generation.
        """
        if frame is None:
            raise InvalidFrameError("Frame is required.")

        frame_type = str(getattr(frame, "frame_type", "") or "").strip()
        if not frame_type:
            raise InvalidFrameError("Frame must have a 'frame_type'.")

        if self._looks_like_bio_or_person_frame(frame_type):
            subject = getattr(frame, "subject", None)

            if not subject:
                raise InvalidFrameError("Bio/person frame requires a 'subject'.")

            subject_name = self._extract_subject_name(subject)
            if not subject_name:
                # Backward-compatible fallback: some models expose `name` directly.
                direct_name = getattr(frame, "name", None)
                if not isinstance(direct_name, str) or not direct_name.strip():
                    raise InvalidFrameError(
                        "Bio/person frame subject must have a non-empty 'name' field."
                    )

    def _looks_like_bio_or_person_frame(self, frame_type: str) -> bool:
        normalized = frame_type.strip().lower()
        return (
            normalized == "bio"
            or normalized.startswith("bio")
            or "person" in normalized
            or normalized == "biography"
        )

    def _extract_subject_name(self, subject: Any) -> str | None:
        if isinstance(subject, dict):
            value = subject.get("name")
            return value.strip() if isinstance(value, str) and value.strip() else None

        value = getattr(subject, "name", None)
        return value.strip() if isinstance(value, str) and value.strip() else None

    def _planner_runtime_available(self) -> bool:
        return self.planner is not None and self.realizer is not None

    def _can_fallback_to_legacy_engine(self) -> bool:
        return self.allow_legacy_engine_fallback and self.engine is not None

    def _merge_debug_info(
        self,
        current: Any,
        defaults: dict[str, Any],
    ) -> dict[str, Any]:
        merged = dict(defaults)

        if isinstance(current, dict):
            merged.update(current)
        elif current is not None:
            merged["raw_debug_info"] = current

        return merged

    def _component_name(self, component: Any) -> str | None:
        if component is None:
            return None
        return component.__class__.__name__