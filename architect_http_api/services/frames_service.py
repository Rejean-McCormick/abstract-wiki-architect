# architect_http_api/services/frames_service.py

from __future__ import annotations

from typing import Dict, List, Optional

from architect_http_api.schemas.frames_metadata import FrameMetadata
from architect_http_api.registry.frames_registry import (
    list_frames as registry_list_frames,
    get_frame as registry_get_frame,
    descriptor_to_dict,
    FrameDescriptor,
)


class FrameNotFoundError(KeyError):
    """
    Raised when a requested frame slug does not exist in the registry.
    """

    def __init__(self, slug: str) -> None:
        super().__init__(f"Unknown frame slug: {slug}")
        self.slug = slug


# ---------------------------------------------------------------------------
# Internal Conversion Helper
# ---------------------------------------------------------------------------

def _to_api_model(descriptor: FrameDescriptor) -> FrameMetadata:
    """
    Convert a Registry 'FrameDescriptor' (dataclass) into an API 'FrameMetadata' (Pydantic).
    
    Handles field name mismatches:
      - descriptor.description -> metadata.short_description
      - descriptor.is_experimental -> metadata.experimental
    """
    # Convert dataclass to dict first
    data = descriptor_to_dict(descriptor)
    
    # Map mismatched fields
    description = data.get("description")
    is_experimental = data.get("is_experimental", False)
    
    # Build Pydantic model, defaulting missing fields (like 'fields') to empty
    return FrameMetadata(
        frame_type=descriptor.frame_type,
        family=descriptor.family,
        title=descriptor.title,
        short_description=description,
        long_description=None, # Registry currently doesn't provide this
        experimental=is_experimental,
        fields=[], # Registry descriptors don't hold field definitions yet; frontend uses schemas
        extra=descriptor.extra
    )


# ---------------------------------------------------------------------------
# Standalone functions (internal logic)
# ---------------------------------------------------------------------------

def list_frames(*, family: Optional[str] = None) -> List[FrameMetadata]:
    """
    Return all registered frames, optionally filtered by frame family.
    Args:
        family:
            Optional canonical frame family name (e.g. "bio", "entity",
            "event", "meta").
            Case-insensitive.

    Returns:
        List of FrameMetadata entries.
    """
    # 1. Get Dataclasses from Registry
    descriptors = registry_list_frames()

    # 2. Filter (Registry returns all)
    if family is not None:
        family_norm = family.lower()
        descriptors = [d for d in descriptors if d.family.lower() == family_norm]

    # 3. Convert to Pydantic Models
    return [_to_api_model(d) for d in descriptors]


def get_frame(slug: str) -> FrameMetadata:
    """
    Return metadata for a single frame identified by its slug.
    The slug is the stable identifier used by the frontend, typically
    mirroring the `frame_type`.

    Args:
        slug:
            Frame slug to look up.

    Raises:
        FrameNotFoundError: if the slug is not registered.

    Returns:
        FrameMetadata instance for the requested frame.
    """
    try:
        descriptor = registry_get_frame(slug)
    except KeyError as exc:
        # registry raises KeyError if not found
        raise FrameNotFoundError(slug) from exc
    
    if descriptor is None:
        raise FrameNotFoundError(slug)
        
    return _to_api_model(descriptor)


def get_families_index() -> Dict[str, List[FrameMetadata]]:
    """
    Return all frames grouped by family.
    This is convenient for UI menus and for debugging the registry.

    Returns:
        Dict mapping family name → list of FrameMetadata.
    """
    index: Dict[str, List[FrameMetadata]] = {}
    
    # Get all frames (converted)
    all_frames = list_frames()
    
    for frame in all_frames:
        index.setdefault(frame.family, []).append(frame)
        
    return index


# ---------------------------------------------------------------------------
# Service Class (Required by __init__.py and Dependency Injection)
# ---------------------------------------------------------------------------

class FramesService:
    """
    Service layer for accessing frame metadata.
    Wraps the registry functions in a class structure for consistency
    with other services (like EntitiesService).
    """

    def list_frames(self, family: Optional[str] = None) -> List[FrameMetadata]:
        return list_frames(family=family)

    def get_frame(self, slug: str) -> FrameMetadata:
        return get_frame(slug)

    def get_families_index(self) -> Dict[str, List[FrameMetadata]]:
        return get_families_index()