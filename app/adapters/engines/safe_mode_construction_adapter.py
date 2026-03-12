# app/adapters/engines/safe_mode_construction_adapter.py
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

import structlog
from collections.abc import Mapping, Sequence

from app.core.domain.models import SurfaceResult
from app.core.domain.planning.construction_plan import ConstructionPlan
from app.core.ports.realizer_port import RealizerSupportStatus

logger = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class _RenderedSurface:
    text: str
    template_used: str
    surface_strategy: str
    used_slots: tuple[str, ...]
    missing_slots: tuple[str, ...]


_LANG_WORDS: dict[str, dict[str, str]] = {
    "en": {
        "be": "is",
        "have": "has",
        "there_is": "there is",
        "and": "and",
        "by": "by",
        "in": "in",
        "who": "who",
        "that": "that",
    },
    "fr": {
        "be": "est",
        "have": "a",
        "there_is": "il y a",
        "and": "et",
        "by": "par",
        "in": "à",
        "who": "qui",
        "that": "que",
    },
    "es": {
        "be": "es",
        "have": "tiene",
        "there_is": "hay",
        "and": "y",
        "by": "por",
        "in": "en",
        "who": "que",
        "that": "que",
    },
    "de": {
        "be": "ist",
        "have": "hat",
        "there_is": "es gibt",
        "and": "und",
        "by": "von",
        "in": "in",
        "who": "der",
        "that": "dass",
    },
    "it": {
        "be": "è",
        "have": "ha",
        "there_is": "c'è",
        "and": "e",
        "by": "da",
        "in": "a",
        "who": "che",
        "that": "che",
    },
    "pt": {
        "be": "é",
        "have": "tem",
        "there_is": "há",
        "and": "e",
        "by": "por",
        "in": "em",
        "who": "que",
        "that": "que",
    },
}

_COPULAR_CONSTRUCTIONS = frozenset(
    {
        "copula_equative_simple",
        "copula_equative_classification",
        "copula_attributive_adj",
        "copula_attributive_np",
        "bio_lead_identity",
    }
)

_EVENTIVE_CONSTRUCTIONS = frozenset(
    {
        "intransitive_event",
        "transitive_event",
        "ditransitive_event",
    }
)

_WRAPPER_CONSTRUCTIONS = frozenset(
    {
        "topic_comment_copular",
        "topic_comment_eventive",
    }
)


def _clean_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _lang_key(lang_code: str) -> str:
    code = _clean_str(lang_code).lower()
    if not code:
        return "en"

    explicit = {
        "eng": "en",
        "fra": "fr",
        "fre": "fr",
        "spa": "es",
        "deu": "de",
        "ger": "de",
        "ita": "it",
        "por": "pt",
    }
    if code in explicit:
        return explicit[code]
    if len(code) >= 2:
        return code[:2]
    return "en"


def _words(lang_code: str) -> dict[str, str]:
    return _LANG_WORDS.get(_lang_key(lang_code), _LANG_WORDS["en"])


def _slot_value_to_text(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, str):
        return value.strip()

    if isinstance(value, Mapping):
        for key in (
            "surface",
            "text",
            "label",
            "name",
            "title",
            "lemma",
            "word",
            "value",
            "qid",
            "id",
        ):
            candidate = value.get(key)
            cleaned = _clean_str(candidate)
            if cleaned:
                return cleaned

        parts: list[str] = []
        for key in (
            "profession",
            "nationality",
            "class",
            "classification",
            "predicate_nominal",
            "adjective",
            "attribute",
            "location",
            "place",
            "object",
            "patient",
        ):
            candidate = value.get(key)
            cleaned = _slot_value_to_text(candidate)
            if cleaned:
                parts.append(cleaned)

        if parts:
            return _normalize_ws(" ".join(parts))

        return ""

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        parts = [_slot_value_to_text(item) for item in value]
        parts = [part for part in parts if part]
        return ", ".join(parts)

    return _clean_str(value)


def _first_slot(plan: ConstructionPlan, *names: str) -> tuple[str, str | None]:
    for name in names:
        if plan.has_slot(name):
            text = _slot_value_to_text(plan.get_slot(name))
            if text:
                return text, name
    return "", None


def _list_slot(plan: ConstructionPlan, *names: str) -> tuple[list[str], str | None]:
    for name in names:
        if not plan.has_slot(name):
            continue

        raw = plan.get_slot(name)
        if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes, bytearray)):
            values = [_slot_value_to_text(item) for item in raw]
            values = [value for value in values if value]
            if values:
                return values, name

        text = _slot_value_to_text(raw)
        if text:
            return [text], name

    return [], None


def _join_list(items: list[str], conj: str) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} {conj} {items[1]}"
    return f"{', '.join(items[:-1])}, {conj} {items[-1]}"


def _default_punctuation(plan: ConstructionPlan) -> str:
    for key in ("sentence_final_punctuation", "punctuation", "ending_punctuation"):
        value = _clean_str(plan.generation_options.get(key))
        if value:
            return value
    return "."


def _finalize_sentence(text: str, plan: ConstructionPlan) -> str:
    text = _normalize_ws(text)
    if not text:
        text = "<unrealizable construction plan>"

    punctuation = _default_punctuation(plan)
    if punctuation and text[-1] not in ".!?":
        text = f"{text}{punctuation}"
    return text


class SafeModeConstructionAdapter:
    """
    Lowest-risk realization backend.

    Characteristics:
    - planner-first: consumes ConstructionPlan directly
    - deterministic and cheap
    - language-light template fallback
    - explicit degraded-mode metadata
    """

    backend_name = "safe_mode"
    renderer_backend = "safe_mode"
    producer = "safe_mode_construction_adapter"

    def supports(self, construction_id: str, lang_code: str) -> bool:
        return bool(_clean_str(construction_id) and _clean_str(lang_code))

    def get_support_status(
        self,
        construction_id: str,
        lang_code: str,
    ) -> RealizerSupportStatus:
        return "fallback_only" if self.supports(construction_id, lang_code) else "unsupported"

    async def realize(
        self,
        construction_plan: ConstructionPlan | Mapping[str, Any],
    ) -> SurfaceResult:
        plan = self._coerce_plan(construction_plan)
        rendered = self._render(plan)

        warnings: list[str] = []
        if rendered.missing_slots:
            warnings.append("missing_slots:" + ",".join(rendered.missing_slots))
        if rendered.template_used == "generic_slot_fallback":
            warnings.append("generic_surface_fallback_used")

        debug_info: dict[str, Any] = {
            "schema_version": "1.0",
            "producer": self.producer,
            "renderer_backend": self.renderer_backend,
            "engine": self.renderer_backend,
            "construction_id": plan.construction_id,
            "input_kind": "construction_plan",
            "fallback_used": True,
            "template_used": rendered.template_used,
            "planning": {
                "topic_entity_id": plan.topic_entity_id,
                "focus_role": plan.focus_role,
                "base_construction_id": plan.base_construction_id,
                "wrapper_construction_id": plan.wrapper_construction_id,
            },
            "realization": {
                "template_used": rendered.template_used,
                "surface_strategy": rendered.surface_strategy,
                "used_slots": list(rendered.used_slots),
                "missing_slots": list(rendered.missing_slots),
            },
        }

        if plan.lexical_bindings:
            debug_info["lexical_resolution"] = {
                "binding_keys": sorted(str(key) for key in plan.lexical_bindings.keys())
            }
        if warnings:
            debug_info["warnings"] = warnings

        text = _finalize_sentence(rendered.text, plan)

        logger.info(
            "safe_mode_realized",
            construction_id=plan.construction_id,
            lang_code=plan.lang_code,
            template_used=rendered.template_used,
            missing_slots=list(rendered.missing_slots),
        )

        return SurfaceResult(
            text=text,
            lang_code=plan.lang_code,
            construction_id=plan.construction_id,
            renderer_backend=self.renderer_backend,
            fallback_used=True,
            tokens=text.split(),
            debug_info=debug_info,
        )

    def _coerce_plan(self, value: ConstructionPlan | Mapping[str, Any]) -> ConstructionPlan:
        if isinstance(value, ConstructionPlan):
            return value.validate()
        if isinstance(value, Mapping):
            return ConstructionPlan.from_dict(value).validate()
        raise TypeError(
            "SafeModeConstructionAdapter.realize expects a ConstructionPlan or mapping."
        )

    def _render(self, plan: ConstructionPlan) -> _RenderedSurface:
        cid = _clean_str(plan.construction_id)

        if cid in _COPULAR_CONSTRUCTIONS:
            return self._render_copular(plan, cid)
        if cid == "copula_locative":
            return self._render_locative(plan)
        if cid == "copula_existential":
            return self._render_existential(plan)
        if cid in {"possession_have", "possession_existential"}:
            return self._render_possession(plan, cid)
        if cid in _EVENTIVE_CONSTRUCTIONS:
            return self._render_eventive(plan, cid)
        if cid == "passive_event":
            return self._render_passive(plan)
        if cid == "coordination_clauses":
            return self._render_coordination(plan)
        if cid in _WRAPPER_CONSTRUCTIONS:
            return self._render_topic_comment(plan, cid)
        if cid == "relative_clause_subject_gap":
            return self._render_relative(plan, subject_gap=True)
        if cid == "relative_clause_object_gap":
            return self._render_relative(plan, subject_gap=False)

        return self._render_generic(plan)

    def _render_copular(
        self,
        plan: ConstructionPlan,
        construction_id: str,
    ) -> _RenderedSurface:
        words = _words(plan.lang_code)

        subject, subject_slot = _first_slot(
            plan,
            "subject",
            "topic",
            "entity",
            "head",
            "theme",
        )

        predicate = ""
        predicate_slot: str | None = None

        if construction_id == "copula_attributive_adj":
            predicate, predicate_slot = _first_slot(
                plan,
                "adjective",
                "attribute",
                "predicate",
                "complement",
            )
        elif construction_id == "copula_attributive_np":
            predicate, predicate_slot = _first_slot(
                plan,
                "predicate_nominal",
                "predicate",
                "classification",
                "class",
                "profession",
            )
        else:
            predicate, predicate_slot = _first_slot(
                plan,
                "predicate",
                "predicate_nominal",
                "classification",
                "class",
                "profession",
                "profession_lemma",
                "nationality",
                "predicate_surface",
                "complement",
            )

        if not predicate:
            nationality, nat_slot = _first_slot(plan, "nationality")
            profession, prof_slot = _first_slot(plan, "profession", "profession_lemma", "class")
            if nationality and profession:
                predicate = f"{nationality} {profession}"
                predicate_slot = f"{nat_slot}+{prof_slot}"

        used = tuple(slot for slot in (subject_slot, predicate_slot) if slot)
        missing = tuple(
            name
            for name, slot in (("subject", subject_slot), ("predicate", predicate_slot))
            if slot is None
        )

        rendered = f"{subject or '<subject?>'} {words['be']} {predicate or '<predicate?>'}"
        return _RenderedSurface(
            text=rendered,
            template_used=f"{construction_id}_template",
            surface_strategy="safe_mode_copular_template",
            used_slots=used,
            missing_slots=missing,
        )

    def _render_locative(self, plan: ConstructionPlan) -> _RenderedSurface:
        words = _words(plan.lang_code)

        subject, subject_slot = _first_slot(plan, "subject", "theme", "entity", "topic")
        location, location_slot = _first_slot(plan, "location", "place", "locative", "site")

        rendered = f"{subject or '<subject?>'} {words['be']} {words['in']} {location or '<location?>'}"
        return _RenderedSurface(
            text=rendered,
            template_used="copula_locative_template",
            surface_strategy="safe_mode_locative_template",
            used_slots=tuple(slot for slot in (subject_slot, location_slot) if slot),
            missing_slots=tuple(
                name
                for name, slot in (("subject", subject_slot), ("location", location_slot))
                if slot is None
            ),
        )

    def _render_existential(self, plan: ConstructionPlan) -> _RenderedSurface:
        words = _words(plan.lang_code)

        existent, existent_slot = _first_slot(
            plan,
            "existent",
            "entity",
            "theme",
            "subject",
            "object",
        )

        rendered = f"{words['there_is']} {existent or '<existent?>'}"
        return _RenderedSurface(
            text=rendered,
            template_used="copula_existential_template",
            surface_strategy="safe_mode_existential_template",
            used_slots=(existent_slot,) if existent_slot else (),
            missing_slots=() if existent_slot else ("existent",),
        )

    def _render_possession(
        self,
        plan: ConstructionPlan,
        construction_id: str,
    ) -> _RenderedSurface:
        words = _words(plan.lang_code)

        possessor, possessor_slot = _first_slot(plan, "possessor", "owner", "subject", "holder")
        possessed, possessed_slot = _first_slot(
            plan,
            "possessed",
            "object",
            "theme",
            "patient",
        )

        rendered = f"{possessor or '<possessor?>'} {words['have']} {possessed or '<possessed?>'}"
        return _RenderedSurface(
            text=rendered,
            template_used=f"{construction_id}_template",
            surface_strategy="safe_mode_possession_template",
            used_slots=tuple(slot for slot in (possessor_slot, possessed_slot) if slot),
            missing_slots=tuple(
                name
                for name, slot in (("possessor", possessor_slot), ("possessed", possessed_slot))
                if slot is None
            ),
        )

    def _render_eventive(
        self,
        plan: ConstructionPlan,
        construction_id: str,
    ) -> _RenderedSurface:
        subject, subject_slot = _first_slot(
            plan,
            "subject",
            "agent",
            "actor",
            "experiencer",
            "theme",
        )
        verb, verb_slot = _first_slot(
            plan,
            "verb",
            "predicate",
            "event",
            "relation",
            "verb_lemma",
            "action",
        )
        obj, object_slot = _first_slot(
            plan,
            "object",
            "patient",
            "theme",
            "target",
            "direct_object",
        )
        indirect, indirect_slot = _first_slot(
            plan,
            "recipient",
            "indirect_object",
            "beneficiary",
            "goal",
        )

        pieces = [subject or "<subject?>", verb or "<verb?>"]
        used_slots = [slot for slot in (subject_slot, verb_slot) if slot]
        missing = [
            name
            for name, slot in (("subject", subject_slot), ("verb", verb_slot))
            if slot is None
        ]

        if construction_id == "ditransitive_event":
            pieces.append(indirect or "<indirect_object?>")
            pieces.append(obj or "<direct_object?>")
            if indirect_slot:
                used_slots.append(indirect_slot)
            if object_slot:
                used_slots.append(object_slot)
            if indirect_slot is None:
                missing.append("indirect_object")
            if object_slot is None:
                missing.append("direct_object")
        elif construction_id == "transitive_event":
            pieces.append(obj or "<object?>")
            if object_slot:
                used_slots.append(object_slot)
            if object_slot is None:
                missing.append("object")
        elif obj:
            pieces.append(obj)
            if object_slot:
                used_slots.append(object_slot)

        return _RenderedSurface(
            text=" ".join(pieces),
            template_used=f"{construction_id}_template",
            surface_strategy="safe_mode_eventive_template",
            used_slots=tuple(dict.fromkeys(used_slots)),
            missing_slots=tuple(dict.fromkeys(missing)),
        )

    def _render_passive(self, plan: ConstructionPlan) -> _RenderedSurface:
        words = _words(plan.lang_code)

        patient, patient_slot = _first_slot(plan, "patient", "object", "subject", "theme")
        verb, verb_slot = _first_slot(plan, "verb", "predicate", "event", "verb_lemma", "action")
        agent, agent_slot = _first_slot(plan, "agent", "subject", "actor")

        pieces = [patient or "<patient?>", words["be"], verb or "<verb?>"]
        if agent:
            pieces.extend([words["by"], agent])

        used = [slot for slot in (patient_slot, verb_slot, agent_slot) if slot]
        missing = [
            name
            for name, slot in (("patient", patient_slot), ("verb", verb_slot))
            if slot is None
        ]

        return _RenderedSurface(
            text=" ".join(pieces),
            template_used="passive_event_template",
            surface_strategy="safe_mode_passive_template",
            used_slots=tuple(dict.fromkeys(used)),
            missing_slots=tuple(dict.fromkeys(missing)),
        )

    def _render_coordination(self, plan: ConstructionPlan) -> _RenderedSurface:
        clauses, clauses_slot = _list_slot(plan, "clauses", "conjuncts", "items", "sentences")
        words = _words(plan.lang_code)

        if not clauses:
            fallback = self._render_generic(plan)
            return _RenderedSurface(
                text=fallback.text,
                template_used="coordination_clauses_template",
                surface_strategy="safe_mode_coordination_generic_fallback",
                used_slots=fallback.used_slots,
                missing_slots=("clauses",),
            )

        return _RenderedSurface(
            text=_join_list(clauses, words["and"]),
            template_used="coordination_clauses_template",
            surface_strategy="safe_mode_coordination_template",
            used_slots=(clauses_slot,) if clauses_slot else (),
            missing_slots=(),
        )

    def _render_topic_comment(
        self,
        plan: ConstructionPlan,
        construction_id: str,
    ) -> _RenderedSurface:
        topic, topic_slot = _first_slot(plan, "topic", "subject", "head", "theme")
        comment, comment_slot = _first_slot(
            plan,
            "comment",
            "predicate",
            "predicate_nominal",
            "attribute",
            "location",
            "event",
            "object",
        )

        if not comment and plan.base_construction_id != plan.construction_id:
            base_render = self._render(
                ConstructionPlan(
                    construction_id=plan.base_construction_id,
                    lang_code=plan.lang_code,
                    slot_map=plan.slot_map,
                    generation_options=plan.generation_options,
                    topic_entity_id=plan.topic_entity_id,
                    focus_role=plan.focus_role,
                    lexical_bindings=plan.lexical_bindings,
                    provenance=plan.provenance,
                    metadata=plan.metadata,
                )
            )
            comment = base_render.text.rstrip(".!?")
            if not comment_slot:
                comment_slot = "base_construction_id"

        rendered = f"{topic or '<topic?>'}, {comment or '<comment?>'}"
        return _RenderedSurface(
            text=rendered,
            template_used=f"{construction_id}_template",
            surface_strategy="safe_mode_topic_comment_template",
            used_slots=tuple(slot for slot in (topic_slot, comment_slot) if slot),
            missing_slots=tuple(
                name
                for name, slot in (("topic", topic_slot), ("comment", comment_slot))
                if slot is None
            ),
        )

    def _render_relative(
        self,
        plan: ConstructionPlan,
        *,
        subject_gap: bool,
    ) -> _RenderedSurface:
        words = _words(plan.lang_code)

        head, head_slot = _first_slot(plan, "head", "topic", "subject", "entity")
        subject, subject_slot = _first_slot(plan, "subject", "agent", "actor")
        verb, verb_slot = _first_slot(plan, "verb", "predicate", "event", "verb_lemma")
        obj, object_slot = _first_slot(plan, "object", "patient", "theme", "target")

        if subject_gap:
            tail = " ".join(part for part in (verb or "<verb?>", obj or "<object?>") if part)
            rendered = f"{head or '<head?>'} {words['who']} {tail}".strip()
            missing = [
                name
                for name, slot in (("head", head_slot), ("verb", verb_slot))
                if slot is None
            ]
            if object_slot is None:
                missing.append("object")
        else:
            tail = " ".join(part for part in (subject or "<subject?>", verb or "<verb?>") if part)
            rendered = f"{head or '<head?>'} {words['that']} {tail}".strip()
            missing = [
                name
                for name, slot in (
                    ("head", head_slot),
                    ("subject", subject_slot),
                    ("verb", verb_slot),
                )
                if slot is None
            ]

        return _RenderedSurface(
            text=rendered,
            template_used="relative_clause_template",
            surface_strategy="safe_mode_relative_clause_template",
            used_slots=tuple(
                slot for slot in (head_slot, subject_slot, verb_slot, object_slot) if slot
            ),
            missing_slots=tuple(dict.fromkeys(missing)),
        )

    def _render_generic(self, plan: ConstructionPlan) -> _RenderedSurface:
        slot_items: list[tuple[str, str]] = []
        for key in plan.slot_keys:
            text = _slot_value_to_text(plan.get_slot(key))
            if text:
                slot_items.append((key, text))

        if slot_items:
            prioritized_values: list[str] = []
            prioritized_keys: list[str] = []

            for preferred in (
                "subject",
                "topic",
                "predicate",
                "predicate_nominal",
                "verb",
                "object",
                "location",
                "comment",
            ):
                for key, text in slot_items:
                    if key == preferred and text not in prioritized_values:
                        prioritized_values.append(text)
                        prioritized_keys.append(key)

            for key, text in slot_items:
                if text not in prioritized_values:
                    prioritized_values.append(text)
                    prioritized_keys.append(key)

            text = " ".join(prioritized_values[:4])
            used_slots = tuple(prioritized_keys[:4])
        else:
            text = plan.construction_id.replace("_", " ")
            used_slots = ()

        return _RenderedSurface(
            text=text,
            template_used="generic_slot_fallback",
            surface_strategy="safe_mode_generic_slot_fallback",
            used_slots=used_slots,
            missing_slots=(),
        )


__all__ = ["SafeModeConstructionAdapter"]