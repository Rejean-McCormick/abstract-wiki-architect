# app/adapters/engines/python_engine_wrapper.py
from __future__ import annotations

import time
from collections.abc import Mapping as ABCMapping
from typing import Any

import structlog

from app.core.domain.exceptions import (
    InvalidFrameError,
    LanguageNotFoundError,
    UnsupportedFrameTypeError,
)
from app.core.domain.models import Frame, Sentence
from app.core.ports.grammar_engine import FrameInput, IGrammarEngine

try:
    from app.core.domain.planning.construction_plan import (
        ConstructionPlan as ConstructionPlanModel,
    )
except Exception:  # pragma: no cover - runtime-safe during staged migration
    ConstructionPlanModel = None

ConstructionPlan = Any if ConstructionPlanModel is None else ConstructionPlanModel

logger = structlog.get_logger()


class PythonGrammarEngine(IGrammarEngine):
    """
    Lightweight pure-Python compatibility / safe-mode renderer.

    Purpose
    -------
    - Primary runtime entrypoint: realize(ConstructionPlan) -> Sentence
    - Migration shim: generate(lang_code, frame) -> Sentence
    - Deterministic fallback renderer when stronger backends are unavailable

    Notes
    -----
    This backend is intentionally conservative and English-oriented. It exists
    to keep the legacy direct-generation path alive while Batch 6 converges on
    the shared construction runtime contract.
    """

    backend_name = "safe_mode"
    engine_name = "python_fast"

    _BIO_ALIASES = frozenset(
        {
            "bio",
            "biography",
            "copula_equative_classification",
            "copula_equative_simple",
            "copula_attributive_np",
            "topic_comment_copular",
        }
    )
    _EVENT_ALIASES = frozenset(
        {
            "event",
            "intransitive_event",
            "transitive_event",
            "ditransitive_event",
            "topic_comment_eventive",
            "causative_event",
            "passive_event",
        }
    )
    _RELATION_ALIASES = frozenset(
        {
            "relational",
            "attribute_property",
            "membership_affiliation",
            "ownership_control",
            "part_whole_composition",
            "role_position_office",
            "spatial_relation",
            "temporal_relation",
            "definition_classification",
        }
    )

    def __init__(self, *, supported_langs: list[str] | None = None) -> None:
        base_langs = supported_langs or ["eng", "en", "debug"]
        self._supported_langs = sorted(
            {self._normalize_lang_code(lang) for lang in base_langs if str(lang).strip()}
        )

    async def realize(self, construction_plan: ConstructionPlan) -> Sentence:
        started = time.perf_counter()
        plan = self._coerce_plan(construction_plan)
        lang_code = self._normalize_lang_code(plan.lang_code)

        if not self._is_supported_language(lang_code):
            raise LanguageNotFoundError(lang_code)

        render_kind = self._classify_construction(plan.construction_id)
        compatibility_mode = self._is_compatibility_plan(plan)
        backend_trace: list[str] = ["validated construction plan"]
        fallback_used = compatibility_mode

        try:
            if render_kind == "bio":
                text = self._render_bio(plan)
                backend_trace.append("rendered bio safe-mode template")
            elif render_kind == "event":
                text = self._render_event(plan)
                backend_trace.append("rendered event safe-mode template")
            elif render_kind == "relation":
                text = self._render_relation(plan)
                backend_trace.append("rendered relation safe-mode template")
            else:
                text = self._render_generic(plan)
                backend_trace.append("rendered generic safe-mode fallback")
                fallback_used = True
        except Exception as exc:  # pragma: no cover - defensive fallback path
            logger.exception(
                "python_engine_render_failed",
                construction_id=plan.construction_id,
                lang_code=lang_code,
                error=str(exc),
            )
            text = self._render_emergency_fallback(plan)
            backend_trace.append("render failed; emitted emergency fallback")
            fallback_used = True

        generation_time_ms = (time.perf_counter() - started) * 1000.0

        return Sentence(
            text=text,
            lang_code=lang_code,
            construction_id=plan.construction_id,
            renderer_backend=self.backend_name,
            fallback_used=fallback_used,
            tokens=text.split(),
            generation_time_ms=generation_time_ms,
            debug_info={
                "construction_id": plan.construction_id,
                "renderer_backend": self.backend_name,
                "engine_backend": self.engine_name,
                "lang_code": lang_code,
                "fallback_used": fallback_used,
                "compatibility_mode": compatibility_mode,
                "render_kind": render_kind,
                "slot_keys": sorted(str(key) for key in plan.slot_map.keys()),
                "backend_trace": backend_trace,
                "wrapper_construction_id": getattr(plan, "wrapper_construction_id", None),
                "base_construction_id": getattr(
                    plan,
                    "base_construction_id",
                    plan.construction_id,
                ),
            },
        )

    async def generate(self, lang_code: str, frame: FrameInput) -> Sentence:
        """
        Legacy compatibility entrypoint.

        This method remains available for older callers, but it now normalizes
        frame input into an internal ConstructionPlan and delegates to realize().
        """
        normalized_frame = self._coerce_frame(frame)
        plan = self._plan_from_legacy_frame(lang_code=lang_code, frame=normalized_frame)
        return await self.realize(plan)

    def supports(self, construction_id: str, lang_code: str) -> bool:
        return bool(str(construction_id).strip()) and self._is_supported_language(lang_code)

    async def get_supported_languages(self) -> list[str]:
        return list(self._supported_langs)

    async def reload(self) -> None:
        # No-op: this backend is code-only and keeps no heavy grammar resources.
        return None

    async def health_check(self) -> bool:
        return True

    # ------------------------------------------------------------------
    # Coercion / normalization helpers
    # ------------------------------------------------------------------

    def _coerce_plan(self, construction_plan: Any) -> ConstructionPlan:
        plan_cls = ConstructionPlanModel
        if plan_cls is None:
            raise RuntimeError(
                "ConstructionPlan is unavailable; the runtime contract files "
                "must be present before PythonGrammarEngine can realize plans."
            )

        if isinstance(construction_plan, plan_cls):
            return construction_plan

        if isinstance(construction_plan, ABCMapping):
            return plan_cls.from_dict(construction_plan)

        if all(
            hasattr(construction_plan, attr)
            for attr in (
                "construction_id",
                "lang_code",
                "slot_map",
            )
        ):
            return plan_cls(
                construction_id=getattr(construction_plan, "construction_id"),
                lang_code=getattr(construction_plan, "lang_code"),
                slot_map=getattr(construction_plan, "slot_map"),
                generation_options=getattr(
                    construction_plan,
                    "generation_options",
                    {},
                ),
                topic_entity_id=getattr(construction_plan, "topic_entity_id", None),
                focus_role=getattr(construction_plan, "focus_role", None),
                lexical_bindings=getattr(construction_plan, "lexical_bindings", {}),
                provenance=getattr(construction_plan, "provenance", {}),
                metadata=getattr(construction_plan, "metadata", {}),
            )

        raise TypeError(
            "PythonGrammarEngine.realize() expects a ConstructionPlan or mapping-like "
            "plan payload."
        )

    def _coerce_frame(self, frame: FrameInput) -> Frame:
        if isinstance(frame, Frame):
            return frame
        if isinstance(frame, ABCMapping):
            return Frame.model_validate(frame)
        raise InvalidFrameError(
            "Legacy generate() expects a Frame instance or dict-like frame payload."
        )

    def _plan_from_legacy_frame(
        self,
        *,
        lang_code: str,
        frame: Frame,
    ) -> ConstructionPlan:
        plan_cls = ConstructionPlanModel
        if plan_cls is None:
            raise RuntimeError("ConstructionPlan is not available at runtime.")

        normalized_type = (frame.normalized_frame_type or frame.frame_type).strip().lower()
        construction_id = self._first_non_empty(
            self._stringify_value(frame.meta.get("construction_id")),
            self._default_construction_id(normalized_type),
        )

        slot_map: dict[str, Any] = {}
        subject_text = self._first_non_empty(
            self._stringify_value(frame.subject.get("name")),
            self._stringify_value(frame.subject.get("label")),
            self._stringify_value(frame.name),
        )
        if subject_text:
            slot_map["subject"] = subject_text

        if frame.is_bio_like:
            profession = self._first_non_empty(
                self._stringify_value(frame.properties.get("profession")),
                self._stringify_value(frame.profession),
                self._stringify_value(frame.subject.get("profession")),
                self._stringify_value(
                    frame.primary_profession_lemmas[0]
                    if frame.primary_profession_lemmas
                    else None
                ),
            )
            nationality = self._first_non_empty(
                self._stringify_value(frame.properties.get("nationality")),
                self._stringify_value(frame.properties.get("origin")),
                self._stringify_value(frame.nationality),
                self._stringify_value(frame.subject.get("nationality")),
                self._stringify_value(
                    frame.nationality_lemmas[0] if frame.nationality_lemmas else None
                ),
            )
            if profession:
                slot_map["profession"] = profession
                slot_map["predicate_nominal"] = profession
            if nationality:
                slot_map["nationality"] = nationality
                slot_map["origin"] = nationality

        elif frame.is_event_like:
            event_text = self._first_non_empty(
                self._stringify_value(frame.properties.get("event")),
                self._stringify_value(frame.event_object),
                self._stringify_value(frame.properties.get("event_object")),
                self._stringify_value(frame.event_type),
            )
            if event_text:
                slot_map["event"] = event_text
            if frame.date:
                slot_map["date"] = frame.date
            if frame.location:
                slot_map["location"] = frame.location

        elif frame.is_relation_like:
            relation = self._first_non_empty(
                self._stringify_value(frame.relation),
                self._stringify_value(frame.properties.get("relation")),
            )
            object_text = self._first_non_empty(
                self._stringify_value(frame.object),
                self._stringify_value(frame.properties.get("object")),
                self._stringify_value(frame.attributes.get("value")),
            )
            if relation:
                slot_map["relation"] = relation
            if object_text:
                slot_map["object"] = object_text
                slot_map["value"] = object_text

        # Preserve extra compatibility fields if they were not already mapped.
        for key, value in frame.properties.items():
            if key not in slot_map and value is not None:
                slot_map[key] = value

        if not slot_map:
            raise UnsupportedFrameTypeError(frame.frame_type)

        metadata = {
            "compatibility_mode": True,
            "compatibility_entrypoint": "generate",
            "legacy_frame_type": frame.frame_type,
            "normalized_frame_type": normalized_type,
        }

        return plan_cls(
            construction_id=construction_id,
            lang_code=self._normalize_lang_code(lang_code),
            slot_map=slot_map,
            generation_options={"source": "legacy_generate"},
            metadata=metadata,
        )

    def _default_construction_id(self, normalized_frame_type: str) -> str:
        if normalized_frame_type == "bio":
            return "copula_equative_classification"
        if normalized_frame_type == "event":
            return "intransitive_event"
        if normalized_frame_type == "relational":
            return "attribute_property"
        return normalized_frame_type or "unknown"

    def _classify_construction(self, construction_id: str) -> str:
        cid = str(construction_id or "").strip().lower()
        if cid in self._BIO_ALIASES:
            return "bio"
        if cid in self._EVENT_ALIASES:
            return "event"
        if cid in self._RELATION_ALIASES:
            return "relation"
        return "generic"

    def _is_supported_language(self, lang_code: str) -> bool:
        normalized = self._normalize_lang_code(lang_code)
        return normalized in self._supported_langs or "debug" in self._supported_langs

    def _is_compatibility_plan(self, plan: ConstructionPlan) -> bool:
        metadata = getattr(plan, "metadata", {}) or {}
        if not isinstance(metadata, ABCMapping):
            return False
        return bool(
            metadata.get("compatibility_mode")
            or metadata.get("compatibility_entrypoint") == "generate"
        )

    @staticmethod
    def _normalize_lang_code(lang_code: Any) -> str:
        return str(lang_code or "").strip().lower()

    # ------------------------------------------------------------------
    # Rendering helpers
    # ------------------------------------------------------------------

    def _render_bio(self, plan: ConstructionPlan) -> str:
        subject = self._lookup_text(plan, "subject", "subject_name", "entity", "topic")
        profession = self._lookup_text(
            plan,
            "profession",
            "predicate_nominal",
            "occupation",
            "role",
            "class",
        )
        nationality = self._lookup_text(plan, "nationality", "origin", "demonym")

        if not subject:
            subject = "<subject?>"

        if profession and nationality:
            return self._cleanup_text(
                f"{subject} is {self._english_article_for(profession)}{profession} "
                f"from {nationality}."
            )
        if profession:
            return self._cleanup_text(
                f"{subject} is {self._english_article_for(profession)}{profession}."
            )
        if nationality:
            return self._cleanup_text(f"{subject} is from {nationality}.")
        return self._cleanup_text(f"{subject} is described in this record.")

    def _render_event(self, plan: ConstructionPlan) -> str:
        subject = self._lookup_text(plan, "subject", "subject_name", "entity", "topic")
        event = self._lookup_text(plan, "event", "event_object", "event_type")
        date = self._lookup_text(plan, "date", "time")
        location = self._lookup_text(plan, "location", "place")

        if not subject:
            subject = "<subject?>"

        if event and date and location:
            return self._cleanup_text(
                f"{subject} participated in {event} on {date} in {location}."
            )
        if event and date:
            return self._cleanup_text(f"{subject} participated in {event} on {date}.")
        if event and location:
            return self._cleanup_text(f"{subject} participated in {event} in {location}.")
        if event:
            return self._cleanup_text(f"{subject} participated in {event}.")
        return self._cleanup_text(f"{subject} has a recorded event.")

    def _render_relation(self, plan: ConstructionPlan) -> str:
        subject = self._lookup_text(plan, "subject", "subject_name", "entity", "topic")
        relation = self._lookup_text(plan, "relation", "predicate", "attribute")
        obj = self._lookup_text(plan, "object", "value", "complement")

        if subject and relation and obj:
            return self._cleanup_text(f"{subject} {relation} {obj}.")
        if subject and obj:
            return self._cleanup_text(f"{subject}: {obj}.")
        return self._render_generic(plan)

    def _render_generic(self, plan: ConstructionPlan) -> str:
        subject = self._lookup_text(plan, "subject", "subject_name", "entity", "topic")
        relation = self._lookup_text(plan, "relation", "predicate", "verb_phrase")
        obj = self._lookup_text(plan, "object", "value", "complement")
        predicate = self._lookup_text(
            plan,
            "predicate_nominal",
            "profession",
            "attribute",
            "description",
            "event",
        )

        if subject and relation and obj:
            return self._cleanup_text(f"{subject} {relation} {obj}.")
        if subject and predicate:
            return self._cleanup_text(f"{subject} {predicate}.")
        if subject and obj:
            return self._cleanup_text(f"{subject}: {obj}.")
        if subject:
            return self._cleanup_text(f"{subject}.")
        summary = self._slot_summary(plan)
        if summary:
            return self._cleanup_text(summary)
        return f"[{plan.construction_id}]"

    def _render_emergency_fallback(self, plan: ConstructionPlan) -> str:
        subject = self._lookup_text(plan, "subject", "subject_name", "entity") or "This item"
        return self._cleanup_text(f"{subject} could not be rendered cleanly.")

    # ------------------------------------------------------------------
    # Slot lookup helpers
    # ------------------------------------------------------------------

    def _lookup_text(self, plan: ConstructionPlan, *slot_names: str) -> str:
        for slot_name in slot_names:
            if hasattr(plan, "get_slot"):
                text = self._stringify_value(plan.get_slot(slot_name))
            else:
                text = self._stringify_value(getattr(plan, "slot_map", {}).get(slot_name))
            if text:
                return text

            lexical_bindings = getattr(plan, "lexical_bindings", {}) or {}
            if isinstance(lexical_bindings, ABCMapping):
                text = self._stringify_value(lexical_bindings.get(slot_name))
                if text:
                    return text
        return ""

    def _slot_summary(self, plan: ConstructionPlan) -> str:
        parts: list[str] = []
        for key, value in getattr(plan, "slot_map", {}).items():
            if key in {"subject", "subject_name"}:
                continue
            text = self._stringify_value(value)
            if text:
                parts.append(f"{key}={text}")
            if len(parts) >= 4:
                break
        return "; ".join(parts)

    def _stringify_value(self, value: Any) -> str:
        if value is None:
            return ""

        if isinstance(value, str):
            return value.strip()

        if isinstance(value, (int, float, bool)):
            return str(value).strip()

        if isinstance(value, ABCMapping):
            for key in (
                "surface",
                "text",
                "label",
                "name",
                "lemma",
                "value",
                "title",
                "id",
                "qid",
            ):
                candidate = value.get(key)
                text = self._stringify_value(candidate)
                if text:
                    return text
            return ""

        if isinstance(value, (list, tuple)):
            items = [self._stringify_value(item) for item in value]
            items = [item for item in items if item]
            return ", ".join(items)

        return str(value).strip()

    @staticmethod
    def _first_non_empty(*values: str) -> str:
        for value in values:
            if value:
                return value
        return ""

    @staticmethod
    def _english_article_for(noun_phrase: str) -> str:
        text = (noun_phrase or "").strip().lower()
        if not text:
            return ""
        if text.startswith(("a ", "an ", "the ")):
            return ""
        return "an " if text[:1] in {"a", "e", "i", "o", "u"} else "a "

    @staticmethod
    def _cleanup_text(text: str) -> str:
        text = " ".join(str(text).split())
        text = text.replace(" ,", ",").replace(" .", ".")
        text = text.replace(" ;", ";").replace(" :", ":")
        return text.strip()


__all__ = ["PythonGrammarEngine"]