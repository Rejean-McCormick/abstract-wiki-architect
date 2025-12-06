# architect_http_api/registry/loaders.py
"""
Thin loading / adapter layer for semantic frames used by the HTTP API.

This module is intentionally minimal. It does two things:

* Re-export the canonical frame registry from :mod:`semantics.all_frames`
  so that HTTP handlers have a single import point for frame metadata.

* Provide convenience helpers to turn incoming JSON-like payloads into
  internal Frame instances using :mod:`semantics.aw_bridge`.

The idea is that anything at the HTTP layer that needs to “load a frame”
should go through this module rather than importing semantics modules
directly. That keeps the public surface small and makes it easier to
evolve the underlying implementation later.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from semantics.aw_bridge import (
    AWFramePayload,
    AWMutablePayload,
    UnknownFrameTypeError,
    frame_from_aw,
    frames_from_aw,
)
from semantics.all_frames import (
    FRAME_FAMILIES,
    FRAME_FAMILY_MAP,
    FRAME_REGISTRY,
    frame_from_dict,
    frame_to_dict,
    get_frame_class,
)
from semantics.types import Frame

JSONMapping = Mapping[str, Any]
JSONMutableMapping = AWMutablePayload
JSONFramePayload = AWFramePayload


__all__ = [
    # Types
    "Frame",
    "JSONMapping",
    "JSONMutableMapping",
    "JSONFramePayload",
    "AWFramePayload",
    "AWMutablePayload",
    "UnknownFrameTypeError",
    # Registry exports
    "FRAME_FAMILIES",
    "FRAME_FAMILY_MAP",
    "FRAME_REGISTRY",
    "get_frame_class",
    "frame_to_dict",
    "frame_from_dict",
    # High-level helpers
    "load_frame",
    "load_frames",
    "frame_to_payload",
]


# ---------------------------------------------------------------------------
# High-level helpers used by the HTTP layer
# ---------------------------------------------------------------------------


def load_frame(obj: Frame | JSONFramePayload) -> Frame:
    """
    Normalize either a Frame instance or a JSON payload into a Frame.

    This is the main entry point you should use in routers / services
    when you get a frame-like object from the outside world.

    Args:
        obj:
            - If it behaves like a Frame (has a ``frame_type`` attribute),
              it is returned as-is.
            - If it is a mapping, it is treated as an AbstractWiki-style
              JSON payload and passed to :func:`semantics.aw_bridge.frame_from_aw`.

    Raises:
        UnknownFrameTypeError: if the payload cannot be mapped to a known frame.
        TypeError: if the input is neither a Frame-like object nor a mapping.
    """
    # Duck-typing: internal frame dataclasses implement the Frame protocol
    # and always have a "frame_type" attribute.
    if hasattr(obj, "frame_type"):
        return obj  # type: ignore[return-value]

    if isinstance(obj, Mapping):
        return frame_from_aw(obj)

    raise TypeError(
        f"load_frame expects a Frame or mapping, got {type(obj)!r}"
    )


def load_frames(
    items: Sequence[Frame | JSONFramePayload] | Iterable[Frame | JSONFramePayload],
) -> list[Frame]:
    """
    Normalize a sequence of Frames and/or JSON payloads into a list of Frames.

    This batches JSON payloads through :func:`semantics.aw_bridge.frames_from_aw`
    for efficiency, while passing through existing Frame instances unchanged.
    """
    frames: list[Frame] = []
    pending_payloads: list[JSONFramePayload] = []

    for item in items:
        if hasattr(item, "frame_type"):
            frames.append(item)  # type: ignore[arg-type]
        elif isinstance(item, Mapping):
            pending_payloads.append(item)  # type: ignore[arg-type]
        else:
            raise TypeError(
                f"load_frames expects Frames or mappings, got {type(item)!r}"
            )

    if pending_payloads:
        frames.extend(frames_from_aw(pending_payloads))

    return frames


def frame_to_payload(frame: Frame) -> dict[str, Any]:
    """
    Convert an internal Frame instance back to a JSON-serializable dict.

    This is a thin wrapper around :func:`semantics.all_frames.frame_to_dict`
    so that HTTP handlers do not need to import semantics directly.
    """
    return frame_to_dict(frame)
