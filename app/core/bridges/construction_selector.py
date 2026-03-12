from __future__ import annotations

from dataclasses import dataclass, field, is_dataclass
from typing import Any, Iterable, Mapping

from app.core.domain.constructions.construction_registry import (
    DEFAULT_CONSTRUCTION_REGISTRY,
    KNOWN_RUNTIME_CONSTRUCTION_IDS,
    ConstructionRegistry,
    ConstructionRegistryError,
    UnknownConstructionError,
)

__all__ = [
    "ConstructionSelectionError",
    "ConstructionSelectionContext",
    "ConstructionSelection",
    "ConstructionSelector",
    "select_construction",
]


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ConstructionSelectionError(RuntimeError):
    """Raised when no valid construction selection can be produced."""


# ---------------------------------------------------------------------------
# Canonical runtime constants
# ---------------------------------------------------------------------------


COPULAR_BASE_CONSTRUCTIONS = frozenset(
    {
        "copula_equative_simple",
        "copula_equative_classification",
        "copula_attributive_adj",
        "copula_attributive_np",
        "copula_locative",
        "copula_existential",
        "possession_have",
        "possession_existential",
    }
)

EVENTIVE_BASE_CONSTRUCTIONS = frozenset(
    {
        "intransitive_event",
        "transitive_event",
        "ditransitive_event",
        "passive_event",
        "coordination_clauses",
    }
)

WRAPPER_SUPPORT: dict[str, frozenset[str]] = {
    "topic_comment_copular": COPULAR_BASE_CONSTRUCTIONS,
    "topic_comment_eventive": EVENTIVE_BASE_CONSTRUCTIONS,
}

EXACT_FRAME_TYPE_TO_BASE: dict[str, str] = {
    # Meta family
    "article": "copula_equative_simple",
    "section": "copula_equative_simple",
    "source": "copula_equative_simple",
    # Aggregate family
    "aggregate.timeline": "coordination_clauses",
    "aggregate.career_summary": "coordination_clauses",
    "aggregate.development": "coordination_clauses",
    "aggregate.reception": "coordination_clauses",
    "aggregate.structure": "coordination_clauses",
    "aggregate.list": "coordination_clauses",
    "aggregate.comparison_set": "coordination_clauses",
    # Relation family
    "relation.definition_classification": "copula_equative_classification",
    "relation.role_position_office": "copula_equative_classification",
    "relation.membership_affiliation": "copula_equative_simple",
    "relation.spatial_relation": "copula_locative",
    "relation.temporal_relation": "copula_equative_simple",
    "relation.ownership_control": "possession_have",
    "relation.attribute_property": "copula_attributive_adj",
    "relation.opinion_evaluation": "copula_attributive_adj",
    "relation.part_whole_composition": "copula_equative_simple",
    "relation.relation_bundle": "copula_equative_simple",
    "relation.causal_influence": "transitive_event",
    "relation.change_of_state": "intransitive_event",
    "relation.communication_statement": "transitive_event",
    "relation.comparative_ranking": "copula_attributive_adj",
    "relation.quantitative_measure": "copula_attributive_np",
}

FRAME_FAMILY_DEFAULTS: dict[str, str] = {
    "entity": "copula_equative_classification",
    "relation": "copula_equative_simple",
    "event": "intransitive_event",
    "aggregate": "coordination_clauses",
    "meta": "copula_equative_simple",
    "bio": "copula_equative_classification",
}

FRAME_TYPES_THAT_DEFAULT_TO_COPULAR_WRAPPER = frozenset(
    {
        "article",
        "section",
        "source",
    }
)

FRAME_TYPES_THAT_DEFAULT_TO_EVENTIVE_WRAPPER = frozenset(
    {
        "aggregate.timeline",
        "aggregate.career_summary",
        "aggregate.development",
        "aggregate.reception",
    }
)

RELATIVE_SUBJECT_ATTACHMENT_VALUES = frozenset(
    {"relative_subject", "subject_gap", "relative_clause_subject_gap"}
)
RELATIVE_OBJECT_ATTACHMENT_VALUES = frozenset(
    {"relative_object", "object_gap", "relative_clause_object_gap"}
)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ConstructionSelectionContext:
    """
    Input context for construction selection.

    The selector accepts a normalized semantic frame plus optional discourse
    and generation hints gathered by the planner.
    """

    frame: Mapping[str, Any] | Any
    lang_code: str
    topic_entity_id: str | None = None
    focus_role: str | None = None
    discourse_mode: str | None = None
    is_first_sentence: bool | None = None
    prefer_topic_wrapper: bool | None = None
    allow_wrappers: bool = True
    attachment_mode: str | None = None
    forced_construction_id: str | None = None
    forced_wrapper_construction_id: str | None = None
    generation_options: Mapping[str, Any] | None = None
    metadata: Mapping[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class ConstructionSelection:
    """
    Final selection decision produced by the bridge.

    `construction_id` is always the outer construction. When a wrapper is
    used, `base_construction_id` records the packaged base construction and
    `wrapper_construction_id` repeats the outer wrapper explicitly for planner
    metadata compatibility.
    """

    construction_id: str
    lang_code: str
    topic_entity_id: str | None = None
    focus_role: str | None = None
    discourse_mode: str | None = None
    base_construction_id: str | None = None
    wrapper_construction_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_wrapper(self) -> bool:
        return bool(self.wrapper_construction_id)

    @property
    def effective_base_construction_id(self) -> str:
        return self.base_construction_id or self.construction_id

    @property
    def fallback_used(self) -> bool:
        return bool(self.metadata.get("fallback_used"))

    def planner_metadata(self) -> dict[str, Any]:
        """
        Return metadata in the planner-facing shape expected by downstream
        planning/runtime contracts.
        """
        out = dict(self.metadata)
        if self.wrapper_construction_id:
            out["wrapper_construction_id"] = self.wrapper_construction_id
        if self.base_construction_id:
            out["base_construction_id"] = self.base_construction_id
        return out


# ---------------------------------------------------------------------------
# Selector implementation
# ---------------------------------------------------------------------------


class ConstructionSelector:
    """
    Rule-based bridge from normalized frames to canonical construction IDs.

    Responsibilities
    ----------------
    - choose a base construction from frame family / subtype / valency
    - decide whether the base should be wrapped as topic-comment packaging
    - preserve explicit relative-clause packaging when requested
    - record deterministic fallback metadata when heuristics are used
    - validate the final choice against the registry when possible

    The selector is deliberately renderer-agnostic: it chooses construction
    meaning and discourse packaging, not surface syntax.
    """

    def __init__(
        self,
        registry: ConstructionRegistry | None = None,
        *,
        strict_registry: bool = False,
    ) -> None:
        self._registry = registry or DEFAULT_CONSTRUCTION_REGISTRY
        self._strict_registry = strict_registry

    def select(
        self,
        frame: Mapping[str, Any] | Any,
        *,
        lang_code: str,
        topic_entity_id: str | None = None,
        focus_role: str | None = None,
        discourse_mode: str | None = None,
        is_first_sentence: bool | None = None,
        prefer_topic_wrapper: bool | None = None,
        allow_wrappers: bool = True,
        attachment_mode: str | None = None,
        forced_construction_id: str | None = None,
        forced_wrapper_construction_id: str | None = None,
        generation_options: Mapping[str, Any] | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> ConstructionSelection:
        context = ConstructionSelectionContext(
            frame=frame,
            lang_code=lang_code,
            topic_entity_id=topic_entity_id,
            focus_role=focus_role,
            discourse_mode=discourse_mode,
            is_first_sentence=is_first_sentence,
            prefer_topic_wrapper=prefer_topic_wrapper,
            allow_wrappers=allow_wrappers,
            attachment_mode=attachment_mode,
            forced_construction_id=forced_construction_id,
            forced_wrapper_construction_id=forced_wrapper_construction_id,
            generation_options=generation_options,
            metadata=metadata,
        )
        return self.select_from_context(context)

    def select_from_context(
        self,
        context: ConstructionSelectionContext,
    ) -> ConstructionSelection:
        frame = context.frame
        frame_type = self._frame_type(frame)
        frame_family = self._frame_family(frame_type)
        merged_generation = self._merge_maps(
            context.generation_options,
            self._mapping_or_none(self._read_value(frame, "generation_options")),
        )
        merged_metadata = self._merge_maps(
            self._mapping_or_none(context.metadata),
            self._mapping_or_none(self._read_value(frame, "metadata")),
            self._mapping_or_none(self._read_value(frame, "extra")),
        )

        topic_entity_id = (
            context.topic_entity_id
            or self._extract_entity_id(self._read_value(frame, "topic"))
            or self._extract_entity_id(self._read_value(frame, "main_entity"))
            or self._extract_entity_id(self._read_value(frame, "subject"))
            or self._first_non_empty_string(
                self._read_value(frame, "topic_entity_id"),
                self._read_value(frame, "main_entity_id"),
                self._read_value(frame, "subject_id"),
            )
        )

        focus_role = (
            context.focus_role
            or self._first_non_empty_string(
                self._read_value(frame, "focus_role"),
                merged_metadata.get("focus_role"),
            )
        )

        discourse_mode = (
            context.discourse_mode
            or self._first_non_empty_string(
                self._read_value(frame, "discourse_mode"),
                merged_generation.get("discourse_mode"),
                merged_metadata.get("discourse_mode"),
            )
        )

        selection_metadata: dict[str, Any] = {
            "selector": "ConstructionSelector",
            "original_frame_type": frame_type,
            "frame_family": frame_family,
        }

        forced_base = context.forced_construction_id or self._first_non_empty_string(
            merged_generation.get("construction_id"),
            merged_metadata.get("construction_id"),
            self._read_value(frame, "construction_id"),
        )

        if forced_base:
            base_construction_id = self._normalize_construction_id(forced_base)
            selection_metadata["selection_reason"] = "forced_construction_id"
        else:
            base_construction_id, inferred_reason, fallback_reason = self._infer_base_construction(
                frame=frame,
                frame_type=frame_type,
                frame_family=frame_family,
                is_first_sentence=context.is_first_sentence,
            )
            selection_metadata["selection_reason"] = inferred_reason
            if fallback_reason:
                selection_metadata["fallback_used"] = True
                selection_metadata["fallback_reason"] = fallback_reason

        # Explicit relative-clause packaging always wins over root-sentence
        # defaults and disables topic-comment wrapping.
        relative_construction_id = self._infer_relative_clause_construction(
            context=context,
            generation_options=merged_generation,
            metadata=merged_metadata,
        )
        if relative_construction_id is not None:
            final = ConstructionSelection(
                construction_id=relative_construction_id,
                lang_code=context.lang_code,
                topic_entity_id=topic_entity_id,
                focus_role=focus_role,
                discourse_mode=discourse_mode,
                base_construction_id=None,
                wrapper_construction_id=None,
                metadata={
                    **selection_metadata,
                    "selection_reason": "explicit_relative_clause_attachment",
                },
            )
            self._validate_selection(final)
            return final

        wrapper_id = self._decide_wrapper(
            base_construction_id=base_construction_id,
            frame=frame,
            frame_type=frame_type,
            frame_family=frame_family,
            topic_entity_id=topic_entity_id,
            discourse_mode=discourse_mode,
            prefer_topic_wrapper=context.prefer_topic_wrapper,
            allow_wrappers=context.allow_wrappers,
            forced_wrapper_construction_id=context.forced_wrapper_construction_id,
            generation_options=merged_generation,
            metadata=merged_metadata,
        )

        if wrapper_id is not None:
            final_metadata = dict(selection_metadata)
            final_metadata["wrapper_construction_id"] = wrapper_id
            final_metadata["base_construction_id"] = base_construction_id
            final = ConstructionSelection(
                construction_id=wrapper_id,
                lang_code=context.lang_code,
                topic_entity_id=topic_entity_id,
                focus_role=focus_role,
                discourse_mode=discourse_mode,
                base_construction_id=base_construction_id,
                wrapper_construction_id=wrapper_id,
                metadata=final_metadata,
            )
        else:
            final = ConstructionSelection(
                construction_id=base_construction_id,
                lang_code=context.lang_code,
                topic_entity_id=topic_entity_id,
                focus_role=focus_role,
                discourse_mode=discourse_mode,
                base_construction_id=None,
                wrapper_construction_id=None,
                metadata=selection_metadata,
            )

        self._validate_selection(final)
        return final

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def _infer_base_construction(
        self,
        *,
        frame: Mapping[str, Any] | Any,
        frame_type: str,
        frame_family: str,
        is_first_sentence: bool | None,
    ) -> tuple[str, str, str | None]:
        exact = EXACT_FRAME_TYPE_TO_BASE.get(frame_type)
        if exact is not None:
            return exact, f"exact_frame_type:{frame_type}", None

        if frame_type == "bio":
            return (
                "copula_equative_classification",
                "bio_entrypoint_default",
                None,
            )

        if frame_family == "entity":
            if is_first_sentence is False and self._looks_eventive_followup(frame):
                return self._infer_eventive_construction(frame), "entity_followup_eventive", None
            return "copula_equative_classification", "entity_family_default", None

        if frame_family == "relation":
            relation_specific = self._infer_relation_construction(frame)
            if relation_specific is not None:
                return relation_specific, "relation_shape_inference", None
            return (
                "copula_equative_simple",
                "relation_family_fallback",
                "relation_family_default",
            )

        if frame_family == "event":
            return self._infer_eventive_construction(frame), "event_valency_inference", None

        if frame_family == "aggregate":
            aggregate_specific = self._infer_aggregate_base_construction(frame_type, frame)
            if aggregate_specific is not None:
                return aggregate_specific, "aggregate_mapping", None
            return (
                "coordination_clauses",
                "aggregate_family_fallback",
                "aggregate_family_default",
            )

        if frame_family == "meta":
            return "copula_equative_simple", "meta_family_default", None

        family_default = FRAME_FAMILY_DEFAULTS.get(frame_family)
        if family_default is not None:
            return (
                family_default,
                f"{frame_family}_family_default",
                f"{frame_family}_family_default",
            )

        # Ultimate safe fallback from the mapping docs:
        # relation-like -> copular, event-like -> intransitive,
        # aggregate/meta -> topic-comment-eventive/coular. Since this layer
        # still selects a base first, use the safe base equivalents.
        if self._looks_event_like(frame, frame_type):
            return "intransitive_event", "ultimate_event_fallback", "ultimate_event_fallback"

        if self._looks_relation_like(frame, frame_type):
            return (
                "copula_equative_simple",
                "ultimate_relation_fallback",
                "ultimate_relation_fallback",
            )

        return (
            "copula_equative_simple",
            "ultimate_generic_fallback",
            "ultimate_generic_fallback",
        )

    def _infer_relation_construction(
        self,
        frame: Mapping[str, Any] | Any,
    ) -> str | None:
        if self._is_passive_requested(frame):
            return "passive_event"

        if self._has_any_value(
            frame,
            "location",
            "place",
            "site",
            "located_in",
            "position_in_space",
        ):
            return "copula_locative"

        if self._has_any_value(
            frame,
            "owner",
            "possessor",
            "possessed",
            "owned_entity",
            "holder",
        ):
            return "possession_have"

        if self._has_any_value(
            frame,
            "adjective",
            "adjective_lemma",
            "property_adjective",
            "evaluation_adjective",
        ):
            return "copula_attributive_adj"

        if self._has_any_value(
            frame,
            "predicate",
            "class_label",
            "profession",
            "office",
            "role",
            "title",
            "nationality",
            "category",
        ):
            if self._has_any_value(frame, "profession", "office", "role", "category", "class_label"):
                return "copula_equative_classification"
            return "copula_equative_simple"

        return None

    def _infer_eventive_construction(
        self,
        frame: Mapping[str, Any] | Any,
    ) -> str:
        if self._is_passive_requested(frame):
            return "passive_event"

        role_names = self._participant_role_names(frame)

        if self._contains_any(
            role_names,
            {"recipient", "beneficiary", "addressee", "indirect_object"},
        ):
            return "ditransitive_event"

        if self._contains_any(
            role_names,
            {"object", "patient", "theme", "direct_object", "target"},
        ):
            return "transitive_event"

        if self._has_any_value(
            frame,
            "object",
            "patient",
            "theme",
            "target",
            "recipient",
            "beneficiary",
        ):
            if self._has_any_value(frame, "recipient", "beneficiary"):
                return "ditransitive_event"
            return "transitive_event"

        return "intransitive_event"

    def _infer_aggregate_base_construction(
        self,
        frame_type: str,
        frame: Mapping[str, Any] | Any,
    ) -> str | None:
        if frame_type in {
            "aggregate.structure",
            "aggregate.list",
            "aggregate.comparison_set",
        }:
            return "coordination_clauses"

        if frame_type in FRAME_TYPES_THAT_DEFAULT_TO_EVENTIVE_WRAPPER:
            return "coordination_clauses"

        items = self._read_value(frame, "items")
        clauses = self._read_value(frame, "clauses")
        events = self._read_value(frame, "events")
        if any(isinstance(v, (list, tuple)) and len(v) > 1 for v in (items, clauses, events)):
            return "coordination_clauses"

        return None

    def _infer_relative_clause_construction(
        self,
        *,
        context: ConstructionSelectionContext,
        generation_options: Mapping[str, Any],
        metadata: Mapping[str, Any],
    ) -> str | None:
        candidates = (
            context.attachment_mode,
            self._first_non_empty_string(
                generation_options.get("attachment_mode"),
                metadata.get("attachment_mode"),
                self._read_value(context.frame, "attachment_mode"),
            ),
            self._first_non_empty_string(
                generation_options.get("construction_role"),
                metadata.get("construction_role"),
            ),
            self._first_non_empty_string(
                generation_options.get("syntactic_mode"),
                metadata.get("syntactic_mode"),
            ),
        )

        normalized_candidates = {
            self._normalize_tag(value)
            for value in candidates
            if isinstance(value, str) and value.strip()
        }

        if normalized_candidates & RELATIVE_SUBJECT_ATTACHMENT_VALUES:
            return "relative_clause_subject_gap"
        if normalized_candidates & RELATIVE_OBJECT_ATTACHMENT_VALUES:
            return "relative_clause_object_gap"
        return None

    def _decide_wrapper(
        self,
        *,
        base_construction_id: str,
        frame: Mapping[str, Any] | Any,
        frame_type: str,
        frame_family: str,
        topic_entity_id: str | None,
        discourse_mode: str | None,
        prefer_topic_wrapper: bool | None,
        allow_wrappers: bool,
        forced_wrapper_construction_id: str | None,
        generation_options: Mapping[str, Any],
        metadata: Mapping[str, Any],
    ) -> str | None:
        if not allow_wrappers:
            return None

        explicit_wrapper = forced_wrapper_construction_id or self._first_non_empty_string(
            generation_options.get("wrapper_construction_id"),
            metadata.get("wrapper_construction_id"),
            self._read_value(frame, "wrapper_construction_id"),
        )
        if explicit_wrapper:
            wrapper_id = self._normalize_construction_id(explicit_wrapper)
            if not self._wrapper_supports(wrapper_id, base_construction_id):
                raise ConstructionSelectionError(
                    f"wrapper {wrapper_id!r} does not support base construction "
                    f"{base_construction_id!r}"
                )
            return wrapper_id

        if not topic_entity_id:
            return None

        if prefer_topic_wrapper is True:
            return self._default_wrapper_for_base(base_construction_id)

        if prefer_topic_wrapper is False:
            return None

        normalized_discourse_mode = self._normalize_tag(discourse_mode)
        if normalized_discourse_mode in {"topic_comment", "topicalized", "summary"}:
            return self._default_wrapper_for_base(base_construction_id)

        if frame_type in FRAME_TYPES_THAT_DEFAULT_TO_COPULAR_WRAPPER:
            if base_construction_id in COPULAR_BASE_CONSTRUCTIONS:
                return "topic_comment_copular"

        if frame_type in FRAME_TYPES_THAT_DEFAULT_TO_EVENTIVE_WRAPPER:
            if base_construction_id in EVENTIVE_BASE_CONSTRUCTIONS:
                return "topic_comment_eventive"

        if frame_family == "meta" and base_construction_id in COPULAR_BASE_CONSTRUCTIONS:
            return "topic_comment_copular"

        # Aggregate sequences and summaries benefit from stable topic packaging,
        # but aggregate.structure/list/comparison_set stay as direct coordination.
        if (
            frame_family == "aggregate"
            and frame_type not in {"aggregate.structure", "aggregate.list", "aggregate.comparison_set"}
            and base_construction_id in EVENTIVE_BASE_CONSTRUCTIONS
        ):
            return "topic_comment_eventive"

        return None

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate_selection(self, selection: ConstructionSelection) -> None:
        construction_id = selection.construction_id
        base_id = selection.base_construction_id

        # Best-effort validation when the registry is not populated yet.
        if len(self._registry) == 0:
            self._validate_against_known_ids(construction_id, base_id)
            return

        try:
            if base_id:
                self._registry.require_supported(
                    construction_id,
                    base_construction_id=base_id,
                )
                self._registry.require(base_id)
            else:
                self._registry.require(construction_id)
        except UnknownConstructionError:
            if self._strict_registry:
                raise
            self._validate_against_known_ids(construction_id, base_id)
        except ConstructionRegistryError:
            raise
        except Exception as exc:
            raise ConstructionSelectionError(
                f"registry validation failed for {construction_id!r}: {exc}"
            ) from exc

    def _validate_against_known_ids(
        self,
        construction_id: str,
        base_id: str | None,
    ) -> None:
        if construction_id not in KNOWN_RUNTIME_CONSTRUCTION_IDS:
            raise ConstructionSelectionError(
                f"unknown construction_id {construction_id!r}"
            )

        if base_id is not None:
            if base_id not in KNOWN_RUNTIME_CONSTRUCTION_IDS:
                raise ConstructionSelectionError(
                    f"unknown base_construction_id {base_id!r}"
                )
            if not self._wrapper_supports(construction_id, base_id):
                raise ConstructionSelectionError(
                    f"wrapper {construction_id!r} does not support base "
                    f"construction {base_id!r}"
                )

    def _wrapper_supports(self, wrapper_id: str, base_id: str) -> bool:
        supported = WRAPPER_SUPPORT.get(wrapper_id)
        if supported is None:
            return False
        return base_id in supported

    def _default_wrapper_for_base(self, base_id: str) -> str | None:
        if base_id in COPULAR_BASE_CONSTRUCTIONS:
            return "topic_comment_copular"
        if base_id in EVENTIVE_BASE_CONSTRUCTIONS:
            return "topic_comment_eventive"
        return None

    # ------------------------------------------------------------------
    # Frame inspection helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _frame_type(frame: Mapping[str, Any] | Any) -> str:
        value = ConstructionSelector._first_non_empty_string(
            ConstructionSelector._read_value(frame, "frame_type"),
            ConstructionSelector._read_value(frame, "type"),
            ConstructionSelector._read_value(frame, "canonical_frame_type"),
            ConstructionSelector._read_value(frame, "kind"),
        )
        return value or "unknown"

    @staticmethod
    def _frame_family(frame_type: str) -> str:
        normalized = ConstructionSelector._normalize_tag(frame_type)
        if not normalized:
            return "unknown"
        if normalized == "bio":
            return "bio"
        if "." in normalized:
            prefix = normalized.split(".", 1)[0]
            if prefix in {"entity", "relation", "event", "aggregate", "meta"}:
                return prefix
        if normalized in {"article", "section", "source"}:
            return "meta"
        return "unknown"

    @staticmethod
    def _looks_event_like(frame: Mapping[str, Any] | Any, frame_type: str) -> bool:
        if frame_type.startswith("event."):
            return True
        return ConstructionSelector._has_any_value_static(
            frame,
            "main_event",
            "event",
            "participants",
            "event_type",
        )

    @staticmethod
    def _looks_relation_like(frame: Mapping[str, Any] | Any, frame_type: str) -> bool:
        if frame_type.startswith("relation."):
            return True
        return ConstructionSelector._has_any_value_static(
            frame,
            "predicate",
            "relation",
            "subject",
            "object",
        )

    @staticmethod
    def _looks_eventive_followup(frame: Mapping[str, Any] | Any) -> bool:
        return ConstructionSelector._has_any_value_static(
            frame,
            "main_event",
            "event",
            "events",
            "timeline",
            "milestones",
        )

    @staticmethod
    def _participant_role_names(frame: Mapping[str, Any] | Any) -> set[str]:
        names: set[str] = set()

        participants = ConstructionSelector._read_value(frame, "participants")
        if isinstance(participants, Mapping):
            for key in participants:
                if isinstance(key, str) and key.strip():
                    names.add(ConstructionSelector._normalize_tag(key))

        main_event = ConstructionSelector._read_value(frame, "main_event")
        if isinstance(main_event, Mapping):
            nested = main_event.get("participants")
            if isinstance(nested, Mapping):
                for key in nested:
                    if isinstance(key, str) and key.strip():
                        names.add(ConstructionSelector._normalize_tag(key))

        return names

    @staticmethod
    def _is_passive_requested(frame: Mapping[str, Any] | Any) -> bool:
        candidates = (
            ConstructionSelector._read_value(frame, "voice"),
            ConstructionSelector._read_value(frame, "preferred_voice"),
            ConstructionSelector._read_value(frame, "discourse_voice"),
        )
        for value in candidates:
            if isinstance(value, str) and ConstructionSelector._normalize_tag(value) == "passive":
                return True
        return False

    @staticmethod
    def _extract_entity_id(value: Any) -> str | None:
        if isinstance(value, str):
            text = value.strip()
            return text or None

        if isinstance(value, Mapping):
            return ConstructionSelector._first_non_empty_string(
                value.get("entity_id"),
                value.get("id"),
                value.get("qid"),
                value.get("wikidata_id"),
            )

        if value is None:
            return None

        return ConstructionSelector._first_non_empty_string(
            getattr(value, "entity_id", None),
            getattr(value, "id", None),
            getattr(value, "qid", None),
            getattr(value, "wikidata_id", None),
        )

    # ------------------------------------------------------------------
    # Generic utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _read_value(obj: Mapping[str, Any] | Any, key: str, default: Any = None) -> Any:
        if obj is None:
            return default

        if isinstance(obj, Mapping):
            return obj.get(key, default)

        getter = getattr(obj, "get", None)
        if callable(getter):
            try:
                return getter(key, default)
            except TypeError:
                pass

        if hasattr(obj, key):
            return getattr(obj, key)

        if is_dataclass(obj):
            try:
                return getattr(obj, key)
            except AttributeError:
                return default

        return default

    @staticmethod
    def _mapping_or_none(value: Any) -> Mapping[str, Any] | None:
        return value if isinstance(value, Mapping) else None

    @staticmethod
    def _merge_maps(*maps: Mapping[str, Any] | None) -> dict[str, Any]:
        merged: dict[str, Any] = {}
        for item in maps:
            if item:
                merged.update(item)
        return merged

    @staticmethod
    def _normalize_tag(value: str | None) -> str:
        if not isinstance(value, str):
            return ""
        return value.strip().lower().replace(" ", "_")

    @staticmethod
    def _normalize_construction_id(value: str) -> str:
        normalized = ConstructionSelector._normalize_tag(value)
        if not normalized:
            raise ConstructionSelectionError("construction_id must not be empty")
        return normalized

    @staticmethod
    def _first_non_empty_string(*values: Any) -> str | None:
        for value in values:
            if isinstance(value, str):
                text = value.strip()
                if text:
                    return text
        return None

    @staticmethod
    def _contains_any(values: Iterable[str], targets: set[str]) -> bool:
        return any(value in targets for value in values)

    @staticmethod
    def _has_any_value(frame: Mapping[str, Any] | Any, *keys: str) -> bool:
        return ConstructionSelector._has_any_value_static(frame, *keys)

    @staticmethod
    def _has_any_value_static(frame: Mapping[str, Any] | Any, *keys: str) -> bool:
        for key in keys:
            value = ConstructionSelector._read_value(frame, key)
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            if isinstance(value, (list, tuple, set, dict)) and len(value) == 0:
                continue
            return True
        return False


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------


def select_construction(
    frame: Mapping[str, Any] | Any,
    *,
    lang_code: str,
    registry: ConstructionRegistry | None = None,
    strict_registry: bool = False,
    topic_entity_id: str | None = None,
    focus_role: str | None = None,
    discourse_mode: str | None = None,
    is_first_sentence: bool | None = None,
    prefer_topic_wrapper: bool | None = None,
    allow_wrappers: bool = True,
    attachment_mode: str | None = None,
    forced_construction_id: str | None = None,
    forced_wrapper_construction_id: str | None = None,
    generation_options: Mapping[str, Any] | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> ConstructionSelection:
    """
    Functional wrapper around :class:`ConstructionSelector`.

    Useful for bridge code that prefers a single-call API.
    """
    selector = ConstructionSelector(
        registry=registry,
        strict_registry=strict_registry,
    )
    return selector.select(
        frame,
        lang_code=lang_code,
        topic_entity_id=topic_entity_id,
        focus_role=focus_role,
        discourse_mode=discourse_mode,
        is_first_sentence=is_first_sentence,
        prefer_topic_wrapper=prefer_topic_wrapper,
        allow_wrappers=allow_wrappers,
        attachment_mode=attachment_mode,
        forced_construction_id=forced_construction_id,
        forced_wrapper_construction_id=forced_wrapper_construction_id,
        generation_options=generation_options,
        metadata=metadata,
    )