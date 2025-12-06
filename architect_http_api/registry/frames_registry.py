# architect_http_api/registry/frames_registry.py
"""
frames_registry.py
-------------------

HTTP-facing registry of semantic frame types.

This module provides a thin, read-only description layer on top of
:mod:`semantics.all_frames`. It is intended for use by the HTTP API and
frontend clients to:

* discover which frame families and frame_type strings are available,
* obtain stable identifiers and human-readable labels for those frames,
* locate (by convention) the JSON schemas that describe each frame type,
* optionally inspect which Python dataclass implements a given frame_type.

The actual semantic definitions live in :mod:`semantics.types` and the
family-specific modules; the global catalogue and registry of types lives
in :mod:`semantics.all_frames`. This module does not introduce any new
frame types; it only exposes metadata in a frontend-friendly form.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence

from semantics.all_frames import (
    FRAME_FAMILIES,
    FRAME_FAMILY_MAP,
    FrameFamily,
    FrameType,
    all_frame_types,
    get_frame_class,
    is_known_frame_type,
)

# ---------------------------------------------------------------------------
# Public data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FrameDescriptor:
    """
    Lightweight description of a semantic frame type for HTTP/frontends.

    Fields
    ------
    frame_type:
        Canonical identifier string, e.g. "bio", "entity.organization",
        "event.conflict", as defined in :mod:`semantics.all_frames`.

    family:
        Frame family string, e.g. "entity", "event", "relation",
        "aggregate", "meta". Also managed by :mod:`semantics.all_frames`.

    title:
        Short human-readable label suitable for menus and UI categories.

    description:
        Longer description of what this frame is for. Safe to display in
        tooltips or documentation panels.

    schema_id:
        Optional logical ID for the JSON schema that describes this
        frame's external JSON shape, e.g. "frames/bio".

    schema_path:
        Optional repository-relative path to the JSON schema file, by
        convention under ``schemas/frames/``. This is purely informative
        for the HTTP layer.

    is_experimental:
        Whether the frame type is considered experimental / draft. This
        allows UIs to visually distinguish mature vs. provisional types.

    frame_class_name:
        Name of the Python class implementing this frame, if known
        (e.g. "BioFrame"). None for catalogue-only types that do not yet
        have a concrete dataclass registered.

    frame_module:
        Module path where the implementing class lives (e.g.
        "semantics.types"), if known.
    """

    frame_type: FrameType
    family: FrameFamily
    title: str
    description: str

    schema_id: Optional[str] = None
    schema_path: Optional[str] = None
    is_experimental: bool = True

    frame_class_name: Optional[str] = None
    frame_module: Optional[str] = None

    extra: Dict[str, Any] = field(default_factory=dict)


# Public type alias: mapping from frame_type → descriptor.
FrameDescriptorMap = Mapping[FrameType, FrameDescriptor]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _default_title_for_frame_type(frame_type: FrameType) -> str:
    """
    Generate a reasonable human-readable title from a canonical frame_type.

    Examples
    --------
    "bio"                  → "Person / biography"
    "entity.organization"  → "Organization (entity)"
    "event.sports"         → "Sports (event)"
    "relation.ownership"   → "Ownership (relation)"
    """
    if frame_type == "bio":
        return "Person / biography"

    if "." in frame_type:
        family, _, rest = frame_type.partition(".")
        # Replace dots/underscores/hyphens with spaces and title-case.
        label = rest.replace(".", " ").replace("_", " ").replace("-", " ").strip()
        if not label:
            return f"{family} frame"
        return f"{label.title()} ({family})"

    # Fallback: best-effort title-case of the whole string.
    label = frame_type.replace(".", " ").replace("_", " ").replace("-", " ").strip()
    return label.title() or frame_type


def _default_description_for_frame_type(frame_type: FrameType, family: FrameFamily) -> str:
    """
    Provide a short, generic description as a fallback.

    The intent is to be safe but informative even if we do not have
    hand-curated prose for a given frame_type yet.
    """
    if frame_type == "bio":
        return "Biography / person-centric frame used for lead sentences about people."

    if family == "entity":
        return f"Entity-centric frame (“{frame_type}”) describing a concrete or abstract entity."
    if family == "event":
        return f"Event-centric frame (“{frame_type}”) describing an event or process."
    if family == "relation":
        return f"Relational frame (“{frame_type}”) expressing a relation between entities, times, or events."
    if family in {"aggregate", "narrative"}:
        return f"Aggregate / narrative frame (“{frame_type}”) organizing multiple facts or events."
    if family == "meta":
        return f"Meta frame (“{frame_type}”) carrying article or citation metadata."

    return f"Semantic frame (“{frame_type}”) in the “{family}” family."


def _schema_path_for_frame_type(frame_type: FrameType) -> str:
    """
    Conventional schema path for a frame type.

    By convention we map dotted identifiers to directory components,
    e.g.:

        "bio"                  → "schemas/frames/bio.json"
        "entity.organization"  → "schemas/frames/entity/organization.json"
    """
    # Replace dots with directory separators.
    parts = frame_type.split(".")
    if len(parts) == 1:
        return f"schemas/frames/{frame_type}.json"
    family = parts[0]
    rest = "/".join(parts[1:])
    return f"schemas/frames/{family}/{rest}.json"


def _build_descriptor(frame_type: FrameType) -> FrameDescriptor:
    """
    Construct a FrameDescriptor for a single frame_type.

    This uses :mod:`semantics.all_frames` as the source of truth for
    families and attempts to resolve the underlying Python class, if any.
    """
    if not is_known_frame_type(frame_type):
        raise KeyError(f"Unknown frame_type {frame_type!r}")

    family: FrameFamily = FRAME_FAMILY_MAP.get(frame_type, "unknown")

    # Try to resolve the registered dataclass for this frame_type.
    frame_cls = None
    try:
        frame_cls = get_frame_class(frame_type)
    except KeyError:
        frame_cls = None

    title = _default_title_for_frame_type(frame_type)
    description = _default_description_for_frame_type(frame_type, family)

    # Simple heuristic: biography is the reference implementation, other
    # families are still experimental until their engines are wired.
    is_experimental = frame_type != "bio"

    schema_id = f"frames/{frame_type}"
    schema_path = _schema_path_for_frame_type(frame_type)

    frame_class_name = frame_cls.__name__ if frame_cls is not None else None
    frame_module = frame_cls.__module__ if frame_cls is not None else None

    return FrameDescriptor(
        frame_type=frame_type,
        family=family,
        title=title,
        description=description,
        schema_id=schema_id,
        schema_path=schema_path,
        is_experimental=is_experimental,
        frame_class_name=frame_class_name,
        frame_module=frame_module,
    )


def _build_registry() -> Dict[FrameType, FrameDescriptor]:
    """
    Build the in-memory descriptor registry from the global frame catalogue.
    """
    registry: Dict[FrameType, FrameDescriptor] = {}

    for ft in all_frame_types():
        registry[ft] = _build_descriptor(ft)

    return registry


# ---------------------------------------------------------------------------
# Global, read-only registry
# ---------------------------------------------------------------------------

#: Global mapping from canonical frame_type string → FrameDescriptor.
_FRAME_REGISTRY: Dict[FrameType, FrameDescriptor] = _build_registry()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_frame_descriptor(frame_type: FrameType) -> FrameDescriptor:
    """
    Look up the descriptor for a single frame_type.

    Raises KeyError if the frame_type is unknown.
    """
    try:
        return _FRAME_REGISTRY[frame_type]
    except KeyError as exc:
        raise KeyError(f"Unknown frame_type {frame_type!r}") from exc


def list_frame_descriptors(*, family: Optional[FrameFamily] = None) -> List[FrameDescriptor]:
    """
    Return all frame descriptors, optionally restricted to a given family.

    Results are sorted by ``frame_type`` for stability.
    """
    if family is None:
        descriptors = list(_FRAME_REGISTRY.values())
    else:
        descriptors = [d for d in _FRAME_REGISTRY.values() if d.family == family]

    descriptors.sort(key=lambda d: d.frame_type)
    return descriptors


def list_families() -> Mapping[FrameFamily, List[FrameDescriptor]]:
    """
    Return a mapping from frame family → list of its frame descriptors.

    The ordering of families matches ``FRAME_FAMILIES.keys()``, and within
    each family frame types are listed in the canonical order declared
    there.
    """
    result: Dict[FrameFamily, List[FrameDescriptor]] = {}

    for family, types in FRAME_FAMILIES.items():
        family_descriptors: List[FrameDescriptor] = []
        for ft in types:
            desc = _FRAME_REGISTRY.get(ft)
            if desc is not None:
                family_descriptors.append(desc)
        result[family] = family_descriptors

    return result


def descriptor_to_dict(descriptor: FrameDescriptor) -> Dict[str, Any]:
    """
    Convert a FrameDescriptor to a plain dict suitable for JSON responses.

    This keeps field names stable for HTTP clients. If you add fields to
    FrameDescriptor, they will automatically appear here via
    :func:`dataclasses.asdict`.
    """
    return asdict(descriptor)


def registry_snapshot() -> Dict[FrameType, Dict[str, Any]]:
    """
    Return a JSON-ready snapshot of the entire registry.

    Mapping: frame_type → descriptor-as-dict.
    """
    return {ft: descriptor_to_dict(desc) for ft, desc in _FRAME_REGISTRY.items()}


__all__ = [
    "FrameDescriptor",
    "FrameDescriptorMap",
    "get_frame_descriptor",
    "list_frame_descriptors",
    "list_families",
    "descriptor_to_dict",
    "registry_snapshot",
]
