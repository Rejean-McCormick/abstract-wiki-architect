# architect_http_api/services/frames_service.py

from __future__ import annotations

from typing import Dict, List, Optional

from ..schemas.frames_metadata import FrameMetadata
from ..registry.frames_registry import (
    list_frames as registry_list_frames,
    get_frame as registry_get_frame,
)


class FrameNotFoundError(KeyError):
    """
    Raised when a requested frame slug does not exist in the registry.
    """

    def __init__(self, slug: str) -> None:
        super().__init__(f"Unknown frame slug: {slug}")
        self.slug = slug


def list_frames(*, family: Optional[str] = None) -> List[FrameMetadata]:
    """
    Return all registered frames, optionally filtered by frame family.

    Args:
        family:
            Optional canonical frame family name (e.g. "bio", "entity",
            "event", "meta"). Case-insensitive.

    Returns:
        List of FrameMetadata entries.
    """
    frames = registry_list_frames()

    if family is None:
        return frames

    family_norm = family.lower()
    return [f for f in frames if f.family.lower() == family_norm]


def get_frame(slug: str) -> FrameMetadata:
    """
    Return metadata for a single frame identified by its slug.

    The slug is the stable identifier used by the frontend, typically
    mirroring the `frame_type` (e.g. "bio", "entity.person",
    "meta.article").

    Args:
        slug:
            Frame slug to look up.

    Raises:
        FrameNotFoundError: if the slug is not registered.

    Returns:
        FrameMetadata instance for the requested frame.
    """
    frame = registry_get_frame(slug)
    if frame is None:
        raise FrameNotFoundError(slug)
    return frame


def get_families_index() -> Dict[str, List[FrameMetadata]]:
    """
    Return all frames grouped by family.

    This is convenient for UI menus and for debugging the registry.

    Returns:
        Dict mapping family name → list of FrameMetadata.
    """
    index: Dict[str, List[FrameMetadata]] = {}
    for frame in registry_list_frames():
        index.setdefault(frame.family, []).append(frame)
    return index
