from __future__ import annotations

"""
Bridge normalized semantic frames into planner-owned sentence plans.

This module is intentionally planner-side and backend-agnostic.

Responsibilities
----------------
- accept a normalized frame (mapping, dataclass, Pydantic model, or plain object),
- canonicalize / inspect its frame family,
- choose a construction (or accept an injected selector),
- package planner metadata and discourse hints,
- emit a `PlannedSentence`.

Non-responsibilities
--------------------
- slot-map construction,
- lexical resolution,
- realization / rendering,
- backend-specific wording or morphology.

Migration notes
---------------
The repository currently contains legacy frame shapes and an older
`discourse.planner.PlannedSentence` dataclass. This bridge is tolerant of both
legacy frames and evolving `PlannedSentence` constructor signatures.
"""

from dataclasses import asdict, dataclass, field, is_dataclass
import inspect
from typing import Any, Callable, Iterable, Mapping, Sequence
from collections.abc import Mapping as ABCMapping


try:
    from app.core.domain.planning.planned_sentence import PlannedSentence
except Exception:
    @dataclass(frozen=True, slots=True)
    class PlannedSentence:  # pragma: no cover - migration fallback
        frame: Any
        construction_id: str
        lang_code: str
        topic_entity_id: str | None = None
        focus_role: str | None = None
        discourse_mode: str | None = None
        generation_options: dict[str, Any] = field(default_factory=dict)
        metadata: dict[str, Any] = field(default_factory=dict)
        source_frame_ids: list[str] | None = None
        priority: int | None = None


__all__ = [
    "FrameToPlanError",
    "InvalidFrameError",
    "UnsupportedFrameTypeError",
    "FrameToPlanBridge",
    "frame_to_plan",
    "frames_to_plans",
]


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class FrameToPlanError(ValueError):
    """Base error for frame-to-plan mapping failures."""


class InvalidFrameError(FrameToPlanError):
    """Raised when the incoming frame cannot be interpreted safely."""


class UnsupportedFrameTypeError(FrameToPlanError):
    """Raised when a frame type is missing or cannot be mapped safely."""


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


SelectionResult = str | Mapping[str, Any]
Selector = Callable[..., SelectionResult]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


_BIOISH_FRAME_TYPES: frozenset[str] = frozenset(
    {
        "bio",
        "biography",
        "entity.person",
        "entity_person",
        "person",
        "entity.person.v1",
        "entity.person.v2",
    }
)

_RELATIONISH_ALIASES: frozenset[str] = frozenset({"relational", "relation"})
_EVENTISH_ALIASES: frozenset[str] = frozenset({"event"})
_METAISH_ALIASES: frozenset[str] = frozenset({"meta"})
_AGGREGATEISH_ALIASES: frozenset[str] = frozenset({"aggregate"})

_DEFAULT_SLOT_BUILDERS: dict[str, str] = {
    "copula_equative_simple": "build_equative_slots",
    "copula_equative_classification": "build_entity_classification_slots",
    "copula_attributive_adj": "build_attributive_adj_slots",
    "copula_attributive_np": "build_attributive_np_slots",
    "copula_locative": "build_spatial_slots",
    "copula_existential": "build_existential_slots",
    "possession_have": "build_possession_slots",
    "possession_existential": "build_possession_slots",
    "topic_comment_copular": "build_topic_comment_copular_slots",
    "topic_comment_eventive": "build_topic_comment_eventive_slots",
    "intransitive_event": "build_intransitive_event_slots",
    "transitive_event": "build_transitive_event_slots",
    "ditransitive_event": "build_ditransitive_event_slots",
    "passive_event": "build_passive_event_slots",
    "relative_clause_subject_gap": "build_relative_clause_subject_gap_slots",
    "relative_clause_object_gap": "build_relative_clause_object_gap_slots",
    "bio_lead_identity": "build_bio_lead_identity_slots",
}


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _normalize_required_str(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise InvalidFrameError(f"{field_name} must be a string, got {type(value).__name__}.")
    normalized = value.strip()
    if not normalized:
        raise InvalidFrameError(f"{field_name} must be a non-empty string.")
    return normalized


def _normalize_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def _safe_mapping(value: Any) -> dict[str, Any]:
    """
    Materialize a best-effort dict view from common frame/container shapes.
    """
    if value is None:
        return {}

    if isinstance(value, ABCMapping):
        return dict(value)

    if hasattr(value, "model_dump") and callable(value.model_dump):
        dumped = value.model_dump()
        if isinstance(dumped, ABCMapping):
            return dict(dumped)

    if hasattr(value, "dict") and callable(value.dict):
        dumped = value.dict()
        if isinstance(dumped, ABCMapping):
            return dict(dumped)

    if is_dataclass(value):
        dumped = asdict(value)
        if isinstance(dumped, ABCMapping):
            return dict(dumped)

    try:
        dumped = vars(value)
    except TypeError:
        return {}

    return {k: v for k, v in dumped.items() if not k.startswith("_")}


def _get_attr_or_key(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, ABCMapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _first_non_empty(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str):
            stripped = value.strip()
            if stripped:
                return stripped
            continue
        return value
    return None


def _extract_entity_id(value: Any) -> str | None:
    if value is None:
        return None

    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None

    if isinstance(value, ABCMapping):
        raw = _first_non_empty(
            value.get("id"),
            value.get("qid"),
            value.get("entity_id"),
            value.get("subject_id"),
        )
        return str(raw).strip() if raw is not None else None

    raw = _first_non_empty(
        getattr(value, "id", None),
        getattr(value, "qid", None),
        getattr(value, "entity_id", None),
        getattr(value, "subject_id", None),
    )
    return str(raw).strip() if raw is not None else None


def _canonicalize_frame_type(raw_frame_type: Any) -> str:
    if not isinstance(raw_frame_type, str):
        raise UnsupportedFrameTypeError("Frame is missing a usable `frame_type`.")

    ft = raw_frame_type.strip().lower()
    if not ft:
        raise UnsupportedFrameTypeError("Frame has an empty `frame_type`.")

    if ft in _BIOISH_FRAME_TYPES:
        return "bio"

    if ft in {"definition", "biographical-definition"}:
        return "relation.definition"

    if ft in _RELATIONISH_ALIASES:
        return "relation.definition"

    if ft in _EVENTISH_ALIASES:
        return "event.generic"

    if ft in _AGGREGATEISH_ALIASES:
        return "aggregate.generic"

    if ft in _METAISH_ALIASES:
        return "meta.generic"

    return ft


def _frame_family(frame_type: str) -> str:
    if frame_type == "bio":
        return "bio"
    if frame_type.startswith("relation."):
        return "relation"
    if frame_type.startswith("event."):
        return "event"
    if frame_type.startswith("aggregate."):
        return "aggregate"
    if frame_type.startswith("meta."):
        return "meta"
    return "other"


def _extract_frame_id(frame: Mapping[str, Any]) -> str | None:
    raw = _first_non_empty(
        frame.get("id"),
        frame.get("frame_id"),
        frame.get("source_frame_id"),
        frame.get("uuid"),
    )
    return str(raw).strip() if raw is not None else None


def _extract_priority(frame: Mapping[str, Any]) -> int | None:
    raw = _first_non_empty(frame.get("priority"), frame.get("rank"))
    if raw is None:
        meta = frame.get("meta")
        if isinstance(meta, ABCMapping):
            raw = _first_non_empty(meta.get("priority"), meta.get("rank"))

    if raw is None:
        return None

    if isinstance(raw, int):
        return raw

    try:
        return int(raw)
    except Exception:
        return None


def _extract_topic_entity_id(frame: Mapping[str, Any]) -> str | None:
    direct = _first_non_empty(
        frame.get("topic_entity_id"),
        frame.get("main_entity_id"),
        frame.get("subject_id"),
        frame.get("entity_id"),
    )
    if direct is not None:
        return str(direct).strip()

    for key in (
        "main_entity",
        "subject",
        "entity",
        "topic",
        "agent",
        "cause",
    ):
        entity_id = _extract_entity_id(frame.get(key))
        if entity_id:
            return entity_id

    return None


def _extract_generation_options(
    frame: Mapping[str, Any],
    *,
    canonical_frame_type: str,
) -> dict[str, Any]:
    options: dict[str, Any] = {}

    raw = frame.get("generation_options")
    if isinstance(raw, ABCMapping):
        options.update(dict(raw))

    meta = frame.get("meta")
    if isinstance(meta, ABCMapping):
        meta_generation = meta.get("generation_options")
        if isinstance(meta_generation, ABCMapping):
            options.update(dict(meta_generation))

    style = _normalize_optional_str(frame.get("style"))
    if style and "register" not in options:
        options["register"] = "formal" if style == "formal" else "neutral"

    family = _frame_family(canonical_frame_type)
    if "tense" not in options:
        if family == "event":
            options["tense"] = "past"
        else:
            options["tense"] = "present"

    allow_fallback = frame.get("allow_fallback")
    if isinstance(allow_fallback, bool) and "allow_fallback" not in options:
        options["allow_fallback"] = allow_fallback

    return options


def _extract_discourse_mode(frame: Mapping[str, Any]) -> str | None:
    value = _first_non_empty(
        frame.get("discourse_mode"),
        frame.get("sentence_mode"),
    )
    if value is not None:
        return str(value).strip()

    meta = frame.get("meta")
    if isinstance(meta, ABCMapping):
        value = _first_non_empty(
            meta.get("discourse_mode"),
            meta.get("sentence_mode"),
        )
        if value is not None:
            return str(value).strip()

    return None


def _wants_topic_wrapper(frame: Mapping[str, Any], discourse_mode: str | None) -> bool:
    if discourse_mode in {"topic_comment", "topic-comment", "topicalized"}:
        return True

    if frame.get("use_topic_wrapper") is True:
        return True

    generation_options = frame.get("generation_options")
    if isinstance(generation_options, ABCMapping):
        if generation_options.get("prefer_topic_comment") is True:
            return True

    meta = frame.get("meta")
    if isinstance(meta, ABCMapping):
        if meta.get("use_topic_wrapper") is True:
            return True

    return False


def _looks_adjectival_attribute(frame: Mapping[str, Any]) -> bool:
    for key in ("predicate_adjective", "adjective", "adjective_lemma"):
        value = frame.get(key)
        if isinstance(value, str) and value.strip():
            return True

    attribute_kind = _normalize_optional_str(frame.get("attribute_kind"))
    if attribute_kind in {"adj", "adjective", "adjectival"}:
        return True

    value_type = _normalize_optional_str(frame.get("value_type"))
    if value_type in {"adj", "adjective", "adjectival"}:
        return True

    return False


def _event_valency(frame: Mapping[str, Any]) -> str:
    voice = _normalize_optional_str(frame.get("voice"))
    if voice == "passive":
        return "passive"

    if any(frame.get(k) is not None for k in ("recipient", "indirect_object", "beneficiary")):
        return "ditransitive"

    if any(frame.get(k) is not None for k in ("object", "theme", "patient", "event_object")):
        return "transitive"

    return "intransitive"


def _default_focus_role(
    frame: Mapping[str, Any],
    *,
    canonical_frame_type: str,
    construction_id: str,
) -> str | None:
    explicit = _normalize_optional_str(frame.get("focus_role"))
    if explicit:
        return explicit

    family = _frame_family(canonical_frame_type)

    if construction_id in {"copula_equative_classification", "copula_equative_simple", "bio_lead_identity"}:
        if frame.get("profession") is not None:
            return "profession"
        if frame.get("nationality") is not None:
            return "nationality"
        return "predicate"

    if construction_id == "copula_locative":
        return "location"

    if construction_id in {"transitive_event", "ditransitive_event", "passive_event", "intransitive_event"}:
        if frame.get("object") is not None or frame.get("event_object") is not None:
            return "object"
        return "event"

    if family == "relation":
        return "predicate"

    return None


def _default_slot_builder_id(construction_id: str, *, base_construction_id: str | None = None) -> str | None:
    if base_construction_id and base_construction_id in _DEFAULT_SLOT_BUILDERS:
        return _DEFAULT_SLOT_BUILDERS[base_construction_id]
    return _DEFAULT_SLOT_BUILDERS.get(construction_id)


def _coerce_selection_result(selection: SelectionResult) -> dict[str, Any]:
    if isinstance(selection, str):
        return {"construction_id": selection}

    if not isinstance(selection, ABCMapping):
        raise FrameToPlanError(
            "Construction selector must return a construction_id string or a mapping."
        )

    result = dict(selection)

    if "construction_id" not in result:
        base = result.get("base_construction_id")
        wrapper = result.get("wrapper_construction_id")
        if isinstance(wrapper, str) and wrapper.strip():
            result["construction_id"] = wrapper.strip()
        elif isinstance(base, str) and base.strip():
            result["construction_id"] = base.strip()
        else:
            raise FrameToPlanError("Construction selector result is missing `construction_id`.")

    return result


def _instantiate_planned_sentence(**kwargs: Any) -> PlannedSentence:
    """
    Instantiate `PlannedSentence` while tolerating migration-era constructor
    differences between legacy and final dataclasses.
    """
    cls = PlannedSentence

    try:
        sig = inspect.signature(cls)
        params = sig.parameters.values()
        accepts_var_kw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params)
        if accepts_var_kw:
            return cls(**kwargs)

        allowed = {p.name for p in params if p.kind in (
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        )}
        filtered = {k: v for k, v in kwargs.items() if k in allowed}
        return cls(**filtered)
    except Exception:
        pass

    # Last-resort migration fallback for very old constructor shapes.
    minimal_order = (
        "frame",
        "construction_id",
        "lang_code",
        "topic_entity_id",
        "focus_role",
        "discourse_mode",
        "generation_options",
        "metadata",
        "source_frame_ids",
        "priority",
    )
    last_error: Exception | None = None
    for cutoff in range(len(minimal_order), 1, -1):
        subset = {k: kwargs[k] for k in minimal_order[:cutoff] if k in kwargs}
        try:
            return cls(**subset)
        except Exception as exc:
            last_error = exc

    raise FrameToPlanError(
        "Unable to instantiate PlannedSentence with the available constructor."
    ) from last_error


# ---------------------------------------------------------------------------
# Default selection logic
# ---------------------------------------------------------------------------


def _default_select_construction(
    frame: Mapping[str, Any],
    *,
    canonical_frame_type: str,
    topic_entity_id: str | None,
    discourse_mode: str | None,
) -> dict[str, Any]:
    family = _frame_family(canonical_frame_type)

    base_construction_id: str
    fallback_used = False
    fallback_reason: str | None = None

    if canonical_frame_type == "bio":
        base_construction_id = "copula_equative_classification"

    elif canonical_frame_type == "relation.definition":
        base_construction_id = "copula_equative_classification"

    elif canonical_frame_type == "relation.attribute":
        base_construction_id = (
            "copula_attributive_adj" if _looks_adjectival_attribute(frame)
            else "copula_attributive_np"
        )

    elif canonical_frame_type == "relation.spatial":
        base_construction_id = "copula_locative"

    elif canonical_frame_type == "relation.ownership":
        base_construction_id = "possession_have"

    elif canonical_frame_type in {
        "relation.membership",
        "relation.role",
        "relation.part_whole",
        "relation.quantitative",
        "relation.comparative",
        "relation.temporal",
        "relation.communication",
        "relation.opinion",
        "relation.bundle",
        "relation.change_of_state",
        "relation.causal",
    }:
        base_construction_id = "copula_equative_simple"

    elif family == "event":
        valency = _event_valency(frame)
        if valency == "passive":
            base_construction_id = "passive_event"
        elif valency == "ditransitive":
            base_construction_id = "ditransitive_event"
        elif valency == "transitive":
            base_construction_id = "transitive_event"
        else:
            base_construction_id = "intransitive_event"

    elif family in {"aggregate", "meta"}:
        base_construction_id = "topic_comment_eventive"
        fallback_used = True
        fallback_reason = f"{family}_frames_default_to_eventive_topic_comment"

    elif family == "relation":
        base_construction_id = "copula_equative_simple"
        fallback_used = True
        fallback_reason = "unknown_relation_frame_fallback"

    else:
        base_construction_id = "copula_equative_simple"
        fallback_used = True
        fallback_reason = "last_resort_fallback"

    construction_id = base_construction_id
    wrapper_construction_id: str | None = None

    if topic_entity_id and _wants_topic_wrapper(frame, discourse_mode):
        if base_construction_id in {
            "copula_equative_simple",
            "copula_equative_classification",
            "copula_attributive_adj",
            "copula_attributive_np",
            "copula_locative",
            "copula_existential",
            "possession_have",
            "possession_existential",
        }:
            construction_id = "topic_comment_copular"
            wrapper_construction_id = construction_id
        elif base_construction_id in {
            "intransitive_event",
            "transitive_event",
            "ditransitive_event",
            "passive_event",
        }:
            construction_id = "topic_comment_eventive"
            wrapper_construction_id = construction_id

    result: dict[str, Any] = {
        "construction_id": construction_id,
        "base_construction_id": base_construction_id,
    }

    if wrapper_construction_id:
        result["wrapper_construction_id"] = wrapper_construction_id

    if fallback_used:
        result["fallback_used"] = True
        result["fallback_reason"] = fallback_reason

    return result


# ---------------------------------------------------------------------------
# Bridge implementation
# ---------------------------------------------------------------------------


class FrameToPlanBridge:
    """
    Explicit bridge from normalized frames to `PlannedSentence`.

    Parameters
    ----------
    selector:
        Optional injected construction selector. It may return either:
        - a construction_id string, or
        - a mapping containing `construction_id` and optional companion data
          such as `base_construction_id`, `wrapper_construction_id`,
          `focus_role`, `metadata`, or `generation_options`.
    """

    def __init__(self, selector: Selector | None = None) -> None:
        self._selector = selector

    def map_frame(
        self,
        frame: Any,
        *,
        lang_code: str,
    ) -> PlannedSentence:
        """
        Map one normalized frame into one planner-owned sentence plan.
        """
        normalized_lang_code = _normalize_required_str(lang_code, field_name="lang_code")
        frame_map = _safe_mapping(frame)
        if not frame_map and not hasattr(frame, "frame_type"):
            raise InvalidFrameError(
                "Frame must be mapping-like, dataclass-like, Pydantic-like, or "
                "an object with a `frame_type` attribute."
            )

        raw_frame_type = _get_attr_or_key(frame, "frame_type", frame_map.get("frame_type"))
        canonical_frame_type = _canonicalize_frame_type(raw_frame_type)
        discourse_mode = _extract_discourse_mode(frame_map)
        topic_entity_id = _extract_topic_entity_id(frame_map)

        selection = (
            self._selector(
                frame_map,
                lang_code=normalized_lang_code,
                canonical_frame_type=canonical_frame_type,
                topic_entity_id=topic_entity_id,
                discourse_mode=discourse_mode,
            )
            if self._selector is not None
            else _default_select_construction(
                frame_map,
                canonical_frame_type=canonical_frame_type,
                topic_entity_id=topic_entity_id,
                discourse_mode=discourse_mode,
            )
        )
        selection_map = _coerce_selection_result(selection)

        construction_id = _normalize_required_str(
            selection_map["construction_id"],
            field_name="construction_id",
        )
        base_construction_id = _normalize_optional_str(selection_map.get("base_construction_id"))
        wrapper_construction_id = _normalize_optional_str(
            selection_map.get("wrapper_construction_id")
        )

        generation_options = _extract_generation_options(
            frame_map,
            canonical_frame_type=canonical_frame_type,
        )
        selection_generation_options = selection_map.get("generation_options")
        if isinstance(selection_generation_options, ABCMapping):
            generation_options.update(dict(selection_generation_options))

        focus_role = (
            _normalize_optional_str(selection_map.get("focus_role"))
            or _default_focus_role(
                frame_map,
                canonical_frame_type=canonical_frame_type,
                construction_id=base_construction_id or construction_id,
            )
        )

        metadata: dict[str, Any] = {
            "canonical_frame_type": canonical_frame_type,
            "original_frame_type": str(raw_frame_type).strip() if raw_frame_type is not None else None,
            "sentence_kind": canonical_frame_type,
            "direct_mapping_used": True,
        }

        if base_construction_id and base_construction_id != construction_id:
            metadata["base_construction_id"] = base_construction_id

        if wrapper_construction_id:
            metadata["wrapper_construction_id"] = wrapper_construction_id

        slot_builder_id = _default_slot_builder_id(
            construction_id,
            base_construction_id=base_construction_id,
        )
        if slot_builder_id:
            metadata["slot_builder_id"] = slot_builder_id

        if selection_map.get("fallback_used") is True:
            metadata["fallback_used"] = True
            if selection_map.get("fallback_reason"):
                metadata["fallback_reason"] = selection_map["fallback_reason"]

        if isinstance(selection_map.get("metadata"), ABCMapping):
            metadata.update(dict(selection_map["metadata"]))

        source_frame_ids: list[str] | None = None
        frame_id = _extract_frame_id(frame_map)
        if frame_id:
            source_frame_ids = [frame_id]

        priority = _extract_priority(frame_map)

        # Planner contract validation at this stage: we can validate the
        # sentence plan fields here, but slot-map validation belongs to the
        # later frame-to-slots / construction-plan phase.
        planned = _instantiate_planned_sentence(
            frame=frame,
            construction_id=construction_id,
            lang_code=normalized_lang_code,
            topic_entity_id=topic_entity_id,
            focus_role=focus_role,
            discourse_mode=discourse_mode,
            generation_options=generation_options,
            metadata=metadata,
            source_frame_ids=source_frame_ids,
            priority=priority,
        )

        return planned

    def map_frames(
        self,
        frames: Iterable[Any],
        *,
        lang_code: str,
    ) -> list[PlannedSentence]:
        """
        Map an iterable of frames into sentence plans, preserving input order.
        """
        return [self.map_frame(frame, lang_code=lang_code) for frame in frames]


# ---------------------------------------------------------------------------
# Public convenience functions
# ---------------------------------------------------------------------------


def frame_to_plan(
    frame: Any,
    *,
    lang_code: str,
    selector: Selector | None = None,
) -> PlannedSentence:
    """
    Functional convenience wrapper over :class:`FrameToPlanBridge`.
    """
    return FrameToPlanBridge(selector=selector).map_frame(frame, lang_code=lang_code)


def frames_to_plans(
    frames: Sequence[Any] | Iterable[Any],
    *,
    lang_code: str,
    selector: Selector | None = None,
) -> list[PlannedSentence]:
    """
    Functional convenience wrapper for batch mapping.
    """
    return FrameToPlanBridge(selector=selector).map_frames(frames, lang_code=lang_code)