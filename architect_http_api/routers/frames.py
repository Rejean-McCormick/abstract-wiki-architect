# architect_http_api/routers/frames.py

from __future__ import annotations

from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException, Query

from ..schemas.frames_metadata import FrameFamilyMeta, FrameTypeMeta
from ..registry.frames_registry import (
    get_frame_families,
    get_frame_schema,
    get_frame_type,
    get_frame_types,
)

router = APIRouter(prefix="/frames", tags=["frames"])


@router.get(
    "/families",
    response_model=List[FrameFamilyMeta],
    summary="List frame families",
)
def list_frame_families() -> List[FrameFamilyMeta]:
    """
    Return all registered frame families.

    Families are coarse groups such as:

    * `entity`
    * `event`
    * `relation`
    * `narrative` / `aggregate`
    * `meta`

    The exact inventory and display labels come from `frames_registry`.
    """
    return get_frame_families()


@router.get(
    "/types",
    response_model=List[FrameTypeMeta],
    summary="List frame types",
)
def list_frame_types(
    family: Optional[str] = Query(
        default=None,
        description="Optional family ID to filter by (e.g. 'entity', 'event', 'relation', 'meta').",
    ),
    status: Optional[str] = Query(
        default=None,
        description=(
            "Optional implementation status filter "
            "(e.g. 'implemented', 'experimental', 'planned')."
        ),
    ),
) -> List[FrameTypeMeta]:
    """
    List all frame types known to the system.

    This is the main discovery endpoint for the frontend:

    * Use it to populate frame-type pickers (e.g. entity vs event vs narrative).
    * Use `family` to only show a subset (e.g. entity frames in an entity-focused UI).
    * Use `status` to hide purely planned or experimental types if needed.
    """
    return get_frame_types(family=family, status=status)


@router.get(
    "/types/{frame_type}",
    response_model=FrameTypeMeta,
    summary="Get metadata for a single frame type",
)
def get_single_frame_type(frame_type: str) -> FrameTypeMeta:
    """
    Return metadata for a single frame type, identified by its canonical
    `frame_type` string (for example: `bio`, `entity.organization`,
    `event.generic`, `aggregate.timeline`).

    This does **not** return the full JSON Schema; use `/frames/schemas/{frame_type}`
    for that.
    """
    try:
        return get_frame_type(frame_type)
    except KeyError as exc:  # `frames_registry` should raise KeyError for unknown types
        raise HTTPException(
            status_code=404,
            detail=f"Unknown frame_type '{frame_type}'.",
        ) from exc


@router.get(
    "/schemas/{frame_type}",
    response_model=dict,
    summary="Get JSON Schema for a frame type",
)
def get_frame_json_schema(frame_type: str) -> dict[str, Any]:
    """
    Return the JSON Schema for a given frame type, if available.

    The schema is used by the frontend to:

    * build dynamic forms,
    * validate user input before calling generation endpoints,
    * surface required vs optional fields.

    If no schema is registered for the requested frame type, a `404` is returned.
    """
    schema = get_frame_schema(frame_type)
    if schema is None:
        raise HTTPException(
            status_code=404,
            detail=f"No JSON Schema registered for frame_type '{frame_type}'.",
        )
    return schema


__all__ = ["router"]
