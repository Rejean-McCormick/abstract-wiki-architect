"""
discourse/planner.py
--------------------

Compatibility discourse planner built on the canonical core planning contract.

Purpose
=======
This module keeps the existing `plan_biography(...)` / `plan_generic(...)`
entrypoints available while migrating sentence planning onto the shared
runtime contract in `app.core.domain.planning.planned_sentence`.

The planner is intentionally:

- heuristic and deterministic,
- construction-oriented rather than renderer-oriented,
- generic across sentence families, with biography-specific ordering as a
  specialized policy,
- backward-friendly for current call sites.

What this module does
=====================

Given semantic frames, it decides:

- linear sentence order,
- a coarse `construction_id`,
- discourse topic anchoring,
- coarse focus/discourse hints,
- planner-level metadata and generation options.

What this module does NOT do
============================

- build slot maps,
- perform lexical resolution,
- realize text,
- own backend-specific syntax or morphology.

Those steps belong downstream in the planner-centered runtime path.
"""

from __future__ import annotations

import inspect
from collections import Counter
from typing import Any, Iterable, Mapping, Optional, Sequence

from app.core.domain.planning.planned_sentence import PlannedSentence


# ---------------------------------------------------------------------------
# Default planning policy
# ---------------------------------------------------------------------------

BIO_FRAME_ORDER: tuple[str, ...] = (
    "definition",
    "biographical-definition",
    "birth",
    "education",
    "career",
    "achievement",
    "award",
    "position",
    "death",
    "other",
)

BIO_DEFINITION_TYPES: frozenset[str] = frozenset(
    {"definition", "biographical-definition"}
)

DEFAULT_CONSTRUCTION_BY_FRAME_TYPE: dict[str, str] = {
    # Copular / identity-ish
    "definition": "copula_equative_simple",
    "biographical-definition": "copula_equative_simple",
    "position": "copula_equative_simple",
    "classification": "copula_equative_classification",
    "class-membership": "copula_equative_classification",
    "instance-of": "copula_equative_classification",
    # Locative / existential / possession
    "location": "copula_locative",
    "located-in": "copula_locative",
    "residence": "copula_locative",
    "headquarters": "copula_locative",
    "existence": "copula_existential",
    "existential": "copula_existential",
    "possession": "possession_have",
    "ownership": "possession_have",
    "has": "possession_have",
    # Topic-comment
    "topic-comment-copular": "topic_comment_copular",
    "topic-comment-eventive": "topic_comment_eventive",
    # Eventive
    "birth": "intransitive_event",
    "death": "intransitive_event",
    "career": "intransitive_event",
    "education": "intransitive_event",
    "appointment": "intransitive_event",
    "achievement": "transitive_event",
    "award": "ditransitive_event",
    # Relative clauses
    "relative-clause-subject": "relative_clause_subject_gap",
    "relative-clause-object": "relative_clause_object_gap",
}

DEFAULT_FOCUS_ROLE_BY_CONSTRUCTION: dict[str, str] = {
    "copula_equative_simple": "predicate_nominal",
    "copula_equative_classification": "predicate_nominal",
    "copula_locative": "location",
    "copula_existential": "existent",
    "possession_have": "possessed",
    "possession_existential": "possessed",
    "topic_comment_copular": "comment",
    "topic_comment_eventive": "comment",
    "intransitive_event": "event",
    "transitive_event": "patient",
    "ditransitive_event": "theme",
    "relative_clause_subject_gap": "head",
    "relative_clause_object_gap": "head",
}


# ---------------------------------------------------------------------------
# Generic frame access helpers
# ---------------------------------------------------------------------------


def _get_field(frame: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if isinstance(frame, Mapping):
            if name in frame:
                return frame[name]
        else:
            if hasattr(frame, name):
                return getattr(frame, name)
    return default


def _frame_type(frame: Any) -> str:
    raw = _get_field(frame, "frame_type", "type", default="other")
    if not isinstance(raw, str):
        return "other"
    value = raw.strip()
    return value if value else "other"


def _main_entity_id(frame: Any) -> Optional[str]:
    raw = _get_field(
        frame,
        "main_entity_id",
        "subject_id",
        "entity_id",
        "topic_entity_id",
        default=None,
    )
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def _frame_id(frame: Any) -> Optional[str]:
    raw = _get_field(
        frame,
        "frame_id",
        "id",
        "source_frame_id",
        "source_id",
        default=None,
    )
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def _source_frame_ids(frame: Any) -> list[str] | None:
    raw = _get_field(frame, "source_frame_ids", default=None)
    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes, bytearray)):
        values = [str(v).strip() for v in raw if str(v).strip()]
        return values or None

    single = _frame_id(frame)
    return [single] if single else None


def _explicit_priority(frame: Any) -> Optional[int]:
    raw = _get_field(frame, "priority", default=None)
    if isinstance(raw, int):
        return raw
    try:
        return int(raw)  # type: ignore[arg-type]
    except Exception:
        return None


def _frame_type_rank(frame_type: str, order: Sequence[str]) -> int:
    try:
        return order.index(frame_type)
    except ValueError:
        return len(order)


def _frame_metadata(frame: Any) -> dict[str, Any]:
    raw = _get_field(frame, "metadata", default=None)
    if isinstance(raw, Mapping):
        return dict(raw)
    return {}


def _frame_generation_options(frame: Any) -> dict[str, Any]:
    raw = _get_field(frame, "generation_options", default=None)
    if isinstance(raw, Mapping):
        return dict(raw)
    return {}


def _frame_discourse_mode(frame: Any) -> Optional[str]:
    raw = _get_field(frame, "discourse_mode", default=None)
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def _preferred_construction_id(frame: Any) -> Optional[str]:
    raw = _get_field(
        frame,
        "construction_id",
        "preferred_construction_id",
        default=None,
    )
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


# ---------------------------------------------------------------------------
# Construction and focus heuristics
# ---------------------------------------------------------------------------


def _guess_construction_id(frame_type: str) -> str:
    if frame_type in DEFAULT_CONSTRUCTION_BY_FRAME_TYPE:
        return DEFAULT_CONSTRUCTION_BY_FRAME_TYPE[frame_type]

    normalized = frame_type.lower().replace("_", "-")

    if any(token in normalized for token in ("relative", "relcl")):
        if "object" in normalized:
            return "relative_clause_object_gap"
        return "relative_clause_subject_gap"

    if any(token in normalized for token in ("locative", "location", "located", "residence")):
        return "copula_locative"

    if any(token in normalized for token in ("existential", "existence")):
        return "copula_existential"

    if any(token in normalized for token in ("possession", "ownership", "possess", "has-")):
        return "possession_have"

    if any(token in normalized for token in ("award", "recipient", "grant")):
        return "ditransitive_event"

    if any(token in normalized for token in ("achievement", "accomplishment", "won", "authored", "founded")):
        return "transitive_event"

    if any(token in normalized for token in ("birth", "death", "career", "education", "event", "appointment")):
        return "intransitive_event"

    if any(token in normalized for token in ("class", "instance", "type-of")):
        return "copula_equative_classification"

    return "copula_equative_simple"


def select_construction_id(
    frame: Any,
    *,
    domain: str = "auto",
    is_lead_sentence: bool = False,
) -> str:
    """
    Choose a construction ID for a frame.

    Rules:
    - explicit per-frame construction override wins,
    - otherwise use frame-type heuristics,
    - keep the result in the canonical runtime identifier space.
    """
    declared = _preferred_construction_id(frame)
    if declared:
        return declared

    frame_type = _frame_type(frame)

    # Keep the lead-sentence hook explicit but conservative.
    # We only emit a specialized biography lead when the frame opts in.
    if (
        domain == "bio"
        and is_lead_sentence
        and frame_type in BIO_DEFINITION_TYPES
        and bool(_get_field(frame, "use_bio_lead", default=False))
    ):
        return "bio_lead_identity"

    return _guess_construction_id(frame_type)


def _guess_focus_role(
    *,
    frame_type: str,
    construction_id: str,
) -> Optional[str]:
    explicit = DEFAULT_FOCUS_ROLE_BY_CONSTRUCTION.get(construction_id)
    if explicit is not None:
        return explicit

    if frame_type in BIO_DEFINITION_TYPES or frame_type == "position":
        return "predicate_nominal"
    if frame_type in {"birth", "death"}:
        return "event_time_place"
    if frame_type == "career":
        return "event"
    if frame_type in {"achievement", "award"}:
        return "achievement"
    return None


# ---------------------------------------------------------------------------
# Planning internals
# ---------------------------------------------------------------------------


def _looks_like_biography(frames: Sequence[Any]) -> bool:
    bioish = {"definition", "biographical-definition", "birth", "death", "career"}
    return any(_frame_type(frame) in bioish for frame in frames)


def _sorted_frames(
    frames: Sequence[Any],
    *,
    frame_order: Sequence[str],
) -> list[Any]:
    keyed: list[tuple[tuple[int, int, int], Any]] = []

    for original_index, frame in enumerate(frames):
        frame_type = _frame_type(frame)
        explicit_priority = _explicit_priority(frame)
        type_rank = _frame_type_rank(frame_type, frame_order)

        # Explicit priority, when present, replaces the default order rank.
        primary = explicit_priority if explicit_priority is not None else type_rank
        keyed.append(((primary, type_rank, original_index), frame))

    keyed.sort(key=lambda item: item[0])
    return [frame for _, frame in keyed]


def _infer_topic_anchor_entity_id(
    frames: Sequence[Any],
    *,
    preferred_frame_types: Optional[set[str]] = None,
) -> Optional[str]:
    if not frames:
        return None

    if preferred_frame_types:
        for frame in frames:
            if _frame_type(frame) in preferred_frame_types:
                entity_id = _main_entity_id(frame)
                if entity_id:
                    return entity_id

    entity_ids = [_main_entity_id(frame) for frame in frames]
    entity_ids = [entity_id for entity_id in entity_ids if entity_id]

    if not entity_ids:
        return None

    counts = Counter(entity_ids)
    most_common_entity, count = counts.most_common(1)[0]
    if count >= 2:
        return most_common_entity

    return entity_ids[0]


def _planned_sentence_param_names() -> frozenset[str]:
    try:
        signature = inspect.signature(PlannedSentence)
    except (TypeError, ValueError):
        return frozenset()
    return frozenset(signature.parameters.keys())


def _make_planned_sentence(
    *,
    frame: Any,
    construction_id: str,
    lang_code: str,
    topic_entity_id: Optional[str],
    focus_role: Optional[str],
    discourse_mode: Optional[str],
    generation_options: Mapping[str, Any],
    metadata: Mapping[str, Any],
    source_frame_ids: list[str] | None,
    priority: Optional[int],
) -> PlannedSentence:
    """
    Instantiate the canonical PlannedSentence while tolerating temporary
    constructor-shape differences during migration.
    """
    param_names = _planned_sentence_param_names()

    common_kwargs: dict[str, Any] = {
        "construction_id": construction_id,
        "lang_code": lang_code,
        "topic_entity_id": topic_entity_id,
        "focus_role": focus_role,
        "discourse_mode": discourse_mode,
        "generation_options": dict(generation_options),
        "metadata": dict(metadata),
        "source_frame_ids": list(source_frame_ids) if source_frame_ids else None,
        "priority": priority,
        "frame": frame,  # legacy compatibility if supported
    }

    if param_names:
        filtered = {k: v for k, v in common_kwargs.items() if k in param_names}
        try:
            return PlannedSentence(**filtered)
        except TypeError:
            pass

    # Fallback for transitional shapes.
    legacy_kwargs = {
        "construction_id": construction_id,
        "topic_entity_id": topic_entity_id,
        "focus_role": focus_role,
        "metadata": dict(metadata),
    }
    if not param_names or "frame" in param_names:
        legacy_kwargs["frame"] = frame
    if not param_names or "lang_code" in param_names:
        legacy_kwargs["lang_code"] = lang_code
    if not param_names or "discourse_mode" in param_names:
        legacy_kwargs["discourse_mode"] = discourse_mode
    if not param_names or "generation_options" in param_names:
        legacy_kwargs["generation_options"] = dict(generation_options)
    if not param_names or "source_frame_ids" in param_names:
        legacy_kwargs["source_frame_ids"] = list(source_frame_ids) if source_frame_ids else None
    if not param_names or "priority" in param_names:
        legacy_kwargs["priority"] = priority

    return PlannedSentence(**legacy_kwargs)


def _build_planned_sentence(
    frame: Any,
    *,
    lang_code: str,
    domain: str,
    order_index: int,
    topic_anchor_entity_id: Optional[str],
    is_lead_sentence: bool,
) -> PlannedSentence:
    frame_type = _frame_type(frame)
    main_entity_id = _main_entity_id(frame)
    construction_id = select_construction_id(
        frame,
        domain=domain,
        is_lead_sentence=is_lead_sentence,
    )
    focus_role = _guess_focus_role(
        frame_type=frame_type,
        construction_id=construction_id,
    )
    discourse_mode = _frame_discourse_mode(frame) or "declarative"

    generation_options = _frame_generation_options(frame)
    metadata = _frame_metadata(frame)

    metadata.setdefault("sentence_kind", frame_type)
    metadata.setdefault("frame_type", frame_type)
    metadata.setdefault("planner_domain", domain)
    metadata.setdefault("planner_module", "discourse.planner")
    metadata.setdefault("order_index", order_index)
    metadata.setdefault("is_lead_sentence", is_lead_sentence)
    metadata.setdefault("main_entity_id", main_entity_id)

    sentence_topic = (
        topic_anchor_entity_id
        if (
            topic_anchor_entity_id is not None
            and main_entity_id is not None
            and main_entity_id == topic_anchor_entity_id
        )
        else None
    )

    return _make_planned_sentence(
        frame=frame,
        construction_id=construction_id,
        lang_code=lang_code,
        topic_entity_id=sentence_topic,
        focus_role=focus_role,
        discourse_mode=discourse_mode,
        generation_options=generation_options,
        metadata=metadata,
        source_frame_ids=_source_frame_ids(frame),
        priority=_explicit_priority(frame),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def plan_biography(
    frames: Iterable[Any],
    *,
    lang_code: str,
) -> list[PlannedSentence]:
    """
    Plan a biography-oriented multi-sentence output.

    Heuristics
    ----------
    - Sort primarily by explicit `priority`, else by BIO_FRAME_ORDER,
      with original input order as a stable tiebreak.
    - Prefer the first definition-like entity as the biography topic anchor.
    - Reuse that topic anchor for later sentences that share the same entity.
    - Choose a canonical runtime `construction_id` for each sentence.

    This function remains intentionally lightweight. It decides sentence-level
    packaging, not slot realization.
    """
    frame_list = list(frames)
    sorted_frames = _sorted_frames(frame_list, frame_order=BIO_FRAME_ORDER)
    topic_anchor_entity_id = _infer_topic_anchor_entity_id(
        sorted_frames,
        preferred_frame_types=set(BIO_DEFINITION_TYPES),
    )

    planned: list[PlannedSentence] = []
    lead_assigned = False

    for order_index, frame in enumerate(sorted_frames):
        frame_type = _frame_type(frame)
        is_lead_sentence = not lead_assigned and frame_type in BIO_DEFINITION_TYPES
        if is_lead_sentence:
            lead_assigned = True

        planned.append(
            _build_planned_sentence(
                frame,
                lang_code=lang_code,
                domain="bio",
                order_index=order_index,
                topic_anchor_entity_id=topic_anchor_entity_id,
                is_lead_sentence=is_lead_sentence,
            )
        )

    return planned


def plan_generic(
    frames: Iterable[Any],
    *,
    lang_code: str,
    domain: str = "auto",
) -> list[PlannedSentence]:
    """
    Generic discourse planning entrypoint.

    Behavior
    --------
    - If `domain == "bio"` or the frames look biography-like, use the
      biography-oriented ordering policy.
    - Otherwise preserve input order and assign conservative construction /
      discourse hints sentence by sentence.
    """
    frame_list = list(frames)

    if domain == "bio" or (domain == "auto" and _looks_like_biography(frame_list)):
        return plan_biography(frame_list, lang_code=lang_code)

    topic_anchor_entity_id = _infer_topic_anchor_entity_id(frame_list)

    planned: list[PlannedSentence] = []
    for order_index, frame in enumerate(frame_list):
        planned.append(
            _build_planned_sentence(
                frame,
                lang_code=lang_code,
                domain=domain if domain != "auto" else "generic",
                order_index=order_index,
                topic_anchor_entity_id=topic_anchor_entity_id,
                is_lead_sentence=(order_index == 0),
            )
        )
    return planned


__all__ = [
    "PlannedSentence",
    "BIO_FRAME_ORDER",
    "plan_biography",
    "plan_generic",
    "select_construction_id",
]