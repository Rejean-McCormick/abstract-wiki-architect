# app\core\domain\semantics\all_frames.py
# semantics\all_frames.py
# semantics/all_frames.py
#
# Central catalogue and registry for all semantic frame families.
#
# This module does three things:
#
#   1. Defines the canonical *frame_type* strings for the full inventory
#      of frame families (entity / event / relation / aggregate / meta).
#   2. Provides utilities to look up the family of a frame type and to
#      list all known frame types.
#   3. Implements a lightweight registry so concrete dataclasses
#      implementing those frame types can be registered and reconstructed
#      from plain dictionaries.
#
# The actual dataclass definitions for frames live in `semantics.types`
# (for the existing core types) and in future modules such as
# `semantics/frames/...`. Those modules should call `register_frame`
# or use `@register_frame_type(...)` to advertise themselves here.
#
# Nothing in the rest of the code base depends on this module yet, so it
# can evolve without breaking the current biography-only pipeline.

from __future__ import annotations

import dataclasses
from dataclasses import asdict
from typing import (
    Any,
    Dict,
    List,
    Mapping,
    Optional,
    Sequence,
    Type,
    TypeVar,
)

from .types import BioFrame, Event

# ---------------------------------------------------------------------------
# Frame type / family catalogue
# ---------------------------------------------------------------------------

FrameType = str
FrameFamily = str

#: Canonical list of frame families and their member frame_type strings.
#:
#: The inventory is intentionally exhaustive and grouped into five
#: high-level families:
#:   - "entity": things we can write articles about
#:   - "event": episodes in time
#:   - "relation": statement-level facts between entities/events
#:   - "aggregate": multi-sentence or multi-event summaries
#:   - "meta": article/section/source metadata
FRAME_FAMILIES: Dict[FrameFamily, List[FrameType]] = {
    # 1–21: Entity-centric frames
    "entity": [
        # 1. Person / Biography frame – existing BioFrame
        "bio",
        # 2. Organization / Group frame
        "entity.organization",
        # 3. Geopolitical entity frame
        "entity.gpe",
        # 4. Other place / geographic feature frame
        "entity.place",
        # 5. Facility / infrastructure frame
        "entity.facility",
        # 6. Astronomical object frame
        "entity.astronomical_object",
        # 7. Species / taxon frame
        "entity.taxon",
        # 8. Chemical / material frame
        "entity.chemical",
        # 9. Physical object / artifact frame
        "entity.artifact",
        # 10. Vehicle / craft frame
        "entity.vehicle",
        # 11. Creative work frame
        "entity.creative_work",
        # 12. Software / website / protocol / standard frame
        "entity.software_or_standard",
        # 13. Product / brand frame
        "entity.product_or_brand",
        # 14. Sports team / club frame
        "entity.sports_team",
        # 15. Competition / tournament / league frame
        "entity.competition",
        # 16. Language frame
        "entity.language",
        # 17. Religion / belief system / ideology frame
        "entity.belief_system",
        # 18. Academic discipline / field / theory frame
        "entity.academic_discipline",
        # 19. Law / treaty / policy / constitution frame
        "entity.law_or_treaty",
        # 20. Project / program / initiative frame
        "entity.project_or_program",
        # 21. Fictional entity / universe / franchise frame
        "entity.fictional_entity",
    ],
    # 22–33: Event-centric frames
    "event": [
        # 22. Generic event frame
        "event.generic",
        # 23. Historical event frame
        "event.historical",
        # 24. Conflict / battle / war frame
        "event.conflict",
        # 25. Election / referendum frame
        "event.election",
        # 26. Disaster / accident frame
        "event.disaster",
        # 27. Scientific / technical milestone frame
        "event.scientific_milestone",
        # 28. Cultural event frame
        "event.cultural",
        # 29. Sports event / match / season frame
        "event.sports",
        # 30. Legal proceeding / case frame
        "event.legal_case",
        # 31. Economic / financial event frame
        "event.economic",
        # 32. Exploration / expedition / mission frame
        "event.exploration",
        # 33. Life-event frame (biographical subfamily)
        "event.life",
    ],
    # 34–48: Relational / statement-level frames
    "relation": [
        # 34. Definition / classification frame
        "relation.definition",
        # 35. Attribute / property frame
        "relation.attribute",
        # 36. Quantitative measure frame
        "relation.quantitative",
        # 37. Comparative / ranking frame
        "relation.comparative",
        # 38. Membership / affiliation frame
        "relation.membership",
        # 39. Role / position / office frame
        "relation.role",
        # 40. Part–whole / composition frame
        "relation.part_whole",
        # 41. Ownership / control frame
        "relation.ownership",
        # 42. Spatial relation frame
        "relation.spatial",
        # 43. Temporal relation frame
        "relation.temporal",
        # 44. Causal / influence frame
        "relation.causal",
        # 45. Change-of-state frame
        "relation.change_of_state",
        # 46. Communication / statement / quote frame
        "relation.communication",
        # 47. Opinion / evaluation frame
        "relation.opinion",
        # 48. Relation-bundle / multi-fact frame
        "relation.bundle",
    ],
    # 49–55: Temporal / narrative / aggregate frames
    "aggregate": [
        # 49. Timeline / chronology frame
        "aggregate.timeline",
        # 50. Career / season / campaign summary frame
        "aggregate.career_summary",
        # 51. Development / evolution frame
        "aggregate.development",
        # 52. Reception / impact frame
        "aggregate.reception",
        # 53. Structure / organization frame
        "aggregate.structure",
        # 54. Comparison-set / contrast frame
        "aggregate.comparison_set",
        # 55. List / enumeration frame
        "aggregate.list",
    ],
    # 56–58: Meta / wrapper frames
    "meta": [
        # 56. Article / document frame
        "meta.article",
        # 57. Section summary frame
        "meta.section_summary",
        # 58. Source / citation frame
        "meta.source",
    ],
}


def _build_family_map(
    families: Mapping[FrameFamily, Sequence[FrameType]],
) -> Dict[FrameType, FrameFamily]:
    """
    Build a reverse map frame_type → family.

    Raises RuntimeError if a frame_type is assigned to multiple families.
    """
    mapping: Dict[FrameType, FrameFamily] = {}
    for family, types in families.items():
        for frame_type in types:
            prev = mapping.get(frame_type)
            if prev is not None and prev != family:
                raise RuntimeError(
                    f"Frame type {frame_type!r} belongs to multiple families: "
                    f"{prev!r}, {family!r}"
                )
            mapping[frame_type] = family
    return mapping


#: Reverse index: frame_type → family name.
FRAME_FAMILY_MAP: Dict[FrameType, FrameFamily] = _build_family_map(FRAME_FAMILIES)


def all_frame_types() -> List[FrameType]:
    """Return a flat list of all canonical frame_type strings."""
    return [frame_type for types in FRAME_FAMILIES.values() for frame_type in types]


def is_known_frame_type(frame_type: FrameType) -> bool:
    """Return True if `frame_type` is part of the canonical inventory."""
    return frame_type in FRAME_FAMILY_MAP


def family_for_type(frame_type: FrameType) -> Optional[FrameFamily]:
    """Return the family name (e.g. 'entity', 'event') for a frame_type."""
    return FRAME_FAMILY_MAP.get(frame_type)


def infer_frame_type(frame: Any, default: FrameType = "other") -> FrameType:
    """
    Heuristically extract `frame_type` from an object or mapping.

    This mirrors the behavior of the internal helpers in `semantics.types`:
    - If `frame` is a mapping, look at `frame["frame_type"]`.
    - Otherwise, try `frame.frame_type`.
    - If missing or not a string, fall back to `default`.
    """
    if isinstance(frame, Mapping):
        ft: Any = frame.get("frame_type")
    else:
        ft = getattr(frame, "frame_type", None)

    if isinstance(ft, str):
        return ft
    return default


def family_for_frame(
    frame: Any, default: Optional[FrameFamily] = None
) -> Optional[FrameFamily]:
    """
    Convenience: given a frame object or mapping, return its family name.

    If the frame has no recognizable `frame_type`, or if that type is not
    in the canonical inventory, returns `default`.
    """
    ft = infer_frame_type(frame, default="other")
    return FRAME_FAMILY_MAP.get(ft, default)


# ---------------------------------------------------------------------------
# Frame registry
# ---------------------------------------------------------------------------

T = TypeVar("T")

#: Runtime registry mapping `frame_type` strings to concrete Python classes.
#:
#: The intent is that each concrete frame dataclass calls `register_frame`
#: (or uses the decorator `@register_frame_type(...)`) in its defining
#: module. This makes it possible to reconstruct frames from serialized
#: dictionaries in a uniform way.
FRAME_REGISTRY: Dict[FrameType, Type[Any]] = {}


def register_frame(
    frame_cls: Type[T],
    *,
    frame_type: Optional[FrameType] = None,
    override: bool = False,
) -> Type[T]:
    """
    Register a frame class under a given frame_type.

    Parameters
    ----------
    frame_cls:
        The dataclass or class implementing the frame.
    frame_type:
        Optional explicit frame_type string. If omitted, we try to read
        `frame_cls.frame_type`. A missing / non-string value is an error.
    override:
        If False (default), attempting to register a different class for
        an already-registered frame_type raises a ValueError. If True, the
        new class silently replaces the old one.

    Returns
    -------
    frame_cls:
        The same class, to make this function usable as a decorator helper.
    """
    ft: Any = (
        frame_type if frame_type is not None else getattr(frame_cls, "frame_type", None)
    )
    if not isinstance(ft, str) or not ft:
        raise ValueError(
            f"Cannot register frame class {frame_cls!r}: "
            f"missing or non-string frame_type (got {ft!r})"
        )

    if not override:
        existing = FRAME_REGISTRY.get(ft)
        if existing is not None and existing is not frame_cls:
            raise ValueError(
                f"Frame type {ft!r} already registered for {existing!r}; "
                f"refusing to overwrite with {frame_cls!r}. "
                f"Pass override=True if this is intentional."
            )

    FRAME_REGISTRY[ft] = frame_cls
    return frame_cls


def register_frame_type(
    frame_type: Optional[FrameType] = None,
    *,
    override: bool = False,
):
    """
    Decorator for registering frame dataclasses.

    Usage examples
    --------------

    Explicit frame_type:

        @register_frame_type("entity.organization")
        @dataclasses.dataclass
        class OrganizationFrame:
            frame_type: ClassVar[str] = "entity.organization"
            ...

    Inferring frame_type from class attribute:

        @register_frame_type()
        @dataclasses.dataclass
        class CompetitionFrame:
            frame_type: ClassVar[str] = "entity.competition"
            ...
    """

    def decorator(cls: Type[T]) -> Type[T]:
        return register_frame(cls, frame_type=frame_type, override=override)

    return decorator


def get_frame_class(frame_type: FrameType) -> Optional[Type[Any]]:
    """Return the registered class for `frame_type`, or None if unknown."""
    return FRAME_REGISTRY.get(frame_type)


def frame_to_dict(frame: Any, *, ensure_type: bool = True) -> Dict[str, Any]:
    """
    Convert a frame object to a plain dictionary.

    - If `frame` is a dataclass instance, `dataclasses.asdict` is used.
    - If it is already a mapping, a shallow `dict(frame)` copy is returned.
    - Otherwise, a ValueError is raised.

    If `ensure_type` is True (default), the resulting mapping is guaranteed
    to contain a string-valued `"frame_type"` key; an existing value is
    preserved, otherwise `infer_frame_type(...)` is used.
    """
    if dataclasses.is_dataclass(frame):
        data: Dict[str, Any] = asdict(frame)
    elif isinstance(frame, Mapping):
        data = dict(frame)
    else:
        raise ValueError(f"Cannot convert object of type {type(frame)!r} to dict")

    if ensure_type and "frame_type" not in data:
        ft = infer_frame_type(frame, default="other")
        data["frame_type"] = ft

    return data


def frame_from_dict(data: Mapping[str, Any]) -> Any:
    """
    Reconstruct a frame object from a dictionary, if possible.

    The function looks for a `"frame_type"` key, uses it to find a
    registered frame class, and then instantiates that class from the
    dictionary fields (excluding `"frame_type"`). Extra keys that are not
    accepted by the class' `__init__` are dropped for dataclasses.

    If there is no `"frame_type"` key, or no class is registered for that
    type, this returns a shallow `dict(data)` copy instead of raising.
    """
    ft_val: Any = data.get("frame_type")
    if not isinstance(ft_val, str):
        # No usable type information; just return the dict.
        return dict(data)

    cls = FRAME_REGISTRY.get(ft_val)
    if cls is None:
        # Unknown frame_type; return the dict unchanged.
        return dict(data)

    kwargs: Dict[str, Any] = dict(data)
    kwargs.pop("frame_type", None)

    if dataclasses.is_dataclass(cls):
        # Filter kwargs to dataclass fields to avoid TypeError.
        field_names = {f.name for f in dataclasses.fields(cls)}  # type: ignore[arg-type]
        kwargs = {k: v for k, v in kwargs.items() if k in field_names}

    try:
        return cls(**kwargs)  # type: ignore[call-arg]
    except TypeError:
        # Fallback: if instantiation fails for any reason, just return the dict.
        return dict(data)


# ---------------------------------------------------------------------------
# Built-in registrations for existing core frames
# ---------------------------------------------------------------------------

# The current code base only has two concrete frame-like dataclasses:
#   - BioFrame (biography / entity summary),
#   - Event (generic event; aliased as EventFrame in `nlg.semantics`).
#
# They do not carry a `frame_type` attribute yet, so we register them
# explicitly under reasonable defaults. These registrations are purely
# advisory for now and do not affect the existing NLG API.

# Person / biography frames
register_frame(BioFrame, frame_type="bio", override=True)

# Generic event frames; other event subtypes can be separate dataclasses
# later and register under more specific frame_type strings if desired.
register_frame(Event, frame_type="event.generic", override=True)


# ---------------------------------------------------------------------------
# Public exports
# ---------------------------------------------------------------------------

__all__ = [
    "FrameType",
    "FrameFamily",
    "FRAME_FAMILIES",
    "FRAME_FAMILY_MAP",
    "FRAME_REGISTRY",
    "all_frame_types",
    "is_known_frame_type",
    "family_for_type",
    "family_for_frame",
    "infer_frame_type",
    "register_frame",
    "register_frame_type",
    "get_frame_class",
    "frame_to_dict",
    "frame_from_dict",
]
