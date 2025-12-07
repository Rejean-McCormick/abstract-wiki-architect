# architect_http_api/registry/frames_registry.py
"""
frames_registry.py
-------------------

HTTP-facing registry of semantic frame types.

This module provides a thin, read-only description layer on top of
:mod:`semantics.all_frames`. It is intended for use by the HTTP API and
frontend clients.
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
    """

    frame_type: FrameType
    family: FrameFamily
    # CHANGE: title and description are now dicts (LocalizedLabel shape)
    title: Dict[str, str]  
    description: Optional[Dict[str, str]]

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


def _default_title_for_frame_type(frame_type: FrameType) -> Dict[str, str]:
    """Returns a LocalizedLabel-compatible dict."""
    if frame_type == "bio":
        text = "Person / biography"
    elif "." in frame_type:
        family, _, rest = frame_type.partition(".")
        label = rest.replace(".", " ").replace("_", " ").replace("-", " ").strip()
        if not label:
            text = f"{family} frame"
        else:
            text = f"{label.title()} ({family})"
    else:
        text = frame_type.replace(".", " ").replace("_", " ").replace("-", " ").strip() or frame_type
    
    return {"text": text}


def _default_description_for_frame_type(frame_type: FrameType, family: FrameFamily) -> Dict[str, str]:
    """Returns a LocalizedLabel-compatible dict."""
    if frame_type == "bio":
        text = "Biography / person-centric frame used for lead sentences about people."
    elif family == "entity":
        text = f"Entity-centric frame (“{frame_type}”) describing a concrete or abstract entity."
    elif family == "event":
        text = f"Event-centric frame (“{frame_type}”) describing an event or process."
    elif family == "relation":
        text = f"Relational frame (“{frame_type}”) expressing a relation between entities, times, or events."
    elif family in {"aggregate", "narrative"}:
        text = f"Aggregate / narrative frame (“{frame_type}”) organizing multiple facts or events."
    elif family == "meta":
        text = f"Meta frame (“{frame_type}”) carrying article or citation metadata."
    else:
        text = f"Semantic frame (“{frame_type}”) in the “{family}” family."
    
    return {"text": text}


def _schema_path_for_frame_type(frame_type: FrameType) -> str:
    parts = frame_type.split(".")
    if len(parts) == 1:
        return f"schemas/frames/{frame_type}.json"
    family = parts[0]
    rest = "/".join(parts[1:])
    return f"schemas/frames/{family}/{rest}.json"


def _build_descriptor(frame_type: FrameType) -> FrameDescriptor:
    if not is_known_frame_type(frame_type):
        raise KeyError(f"Unknown frame_type {frame_type!r}")

    family: FrameFamily = FRAME_FAMILY_MAP.get(frame_type, "unknown")

    frame_cls = None
    try:
        frame_cls = get_frame_class(frame_type)
    except KeyError:
        frame_cls = None

    title = _default_title_for_frame_type(frame_type)
    description = _default_description_for_frame_type(frame_type, family)
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
    registry: Dict[FrameType, FrameDescriptor] = {}
    for ft in all_frame_types():
        registry[ft] = _build_descriptor(ft)
    return registry


# ---------------------------------------------------------------------------
# Global, read-only registry
# ---------------------------------------------------------------------------

_FRAME_REGISTRY: Dict[FrameType, FrameDescriptor] = _build_registry()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_frame_descriptor(frame_type: FrameType) -> FrameDescriptor:
    try:
        return _FRAME_REGISTRY[frame_type]
    except KeyError as exc:
        raise KeyError(f"Unknown frame_type {frame_type!r}") from exc


def list_frame_descriptors(
    *, 
    family: Optional[FrameFamily] = None, 
    status: Optional[str] = None
) -> List[FrameDescriptor]:
    descriptors = list(_FRAME_REGISTRY.values())

    if family is not None:
        descriptors = [d for d in descriptors if d.family == family]

    if status is not None:
        status_norm = status.lower().strip()
        if status_norm == 'experimental':
            descriptors = [d for d in descriptors if d.is_experimental]
        elif status_norm in ('stable', 'implemented', 'production'):
            descriptors = [d for d in descriptors if not d.is_experimental]

    descriptors.sort(key=lambda d: d.frame_type)
    return descriptors


def list_families() -> Mapping[FrameFamily, List[FrameDescriptor]]:
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
    return asdict(descriptor)


def registry_snapshot() -> Dict[FrameType, Dict[str, Any]]:
    return {ft: descriptor_to_dict(desc) for ft, desc in _FRAME_REGISTRY.items()}


# ---------------------------------------------------------------------------
# Compatibility Aliases
# ---------------------------------------------------------------------------

list_frames = list_frame_descriptors
get_frame = get_frame_descriptor
get_frame_type = get_frame_descriptor
get_frame_types = list_frame_descriptors

def get_frame_schema(frame_type: str) -> Optional[Dict[str, Any]]:
    try:
        desc = get_frame_descriptor(frame_type)
        return {
            "$id": desc.schema_id,
            "type": "object",
            "properties": {},
            "description": desc.description.get("text") if desc.description else ""
        }
    except KeyError:
        return None

def get_frame_families() -> List[Dict[str, Any]]:
    families_map = list_families()
    return [
        {
            "family": fam,
            "label": {"text": fam.title()},
            "frame_types": [descriptor_to_dict(fd) for fd in fds]
        }
        for fam, fds in families_map.items()
    ]


__all__ = [
    "FrameDescriptor",
    "FrameDescriptorMap",
    "get_frame_descriptor",
    "list_frame_descriptors",
    "list_families",
    "descriptor_to_dict",
    "registry_snapshot",
    "list_frames",
    "get_frame",
    "get_frame_type",
    "get_frame_types",
    "get_frame_schema",
    "get_frame_families",
]