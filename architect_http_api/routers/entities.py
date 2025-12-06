# architect_http_api/routers/entities.py

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from architect_http_api.db.session import get_session
from architect_http_api.schemas.entities import (
    EntityCreate,
    EntityUpdate,
    EntityRead,
)
from architect_http_api.services.entities_service import EntitiesService

router = APIRouter(prefix="/entities", tags=["entities"])


def get_entities_service(session: Session = Depends(get_session)) -> EntitiesService:
    """
    Dependency-injected factory for EntitiesService.

    Keeping this in one place makes it easy to:
    - swap the implementation in tests (override_dependency),
    - attach logging / tracing later.
    """
    return EntitiesService(session=session)


@router.get(
    "/",
    response_model=List[EntityRead],
    summary="List entities",
    description=(
        "Return all saved entities, optionally filtered by search text and/or frame type. "
        "This is what powers the Abstract Wiki Architect entity list view."
    ),
)
def list_entities(
    *,
    service: EntitiesService = Depends(get_entities_service),
    search: Optional[str] = Query(
        None,
        description="Optional free-text search over name, slug, description, etc.",
    ),
    frame_type: Optional[str] = Query(
        None,
        description="Optional frame-type filter (e.g. 'bio', 'event', 'relational').",
    ),
) -> List[EntityRead]:
    return service.list_entities(search=search, frame_type=frame_type)


@router.post(
    "/",
    response_model=EntityRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create an entity",
    description=(
        "Create a new saved entity (workspace card). "
        "The payload typically includes a name/label, the underlying frame slug, "
        "and a JSON blob of frame inputs."
    ),
)
def create_entity(
    *,
    service: EntitiesService = Depends(get_entities_service),
    payload: EntityCreate,
) -> EntityRead:
    return service.create_entity(payload)


@router.get(
    "/{entity_id}",
    response_model=EntityRead,
    summary="Get a single entity",
    description="Fetch a single saved entity by its numeric id.",
)
def get_entity(
    *,
    entity_id: int,
    service: EntitiesService = Depends(get_entities_service),
) -> EntityRead:
    entity = service.get_entity(entity_id)
    if entity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found",
        )
    return entity


@router.put(
    "/{entity_id}",
    response_model=EntityRead,
    summary="Update an entity",
    description="Replace/update the stored data for an existing entity.",
)
def update_entity(
    *,
    entity_id: int,
    payload: EntityUpdate,
    service: EntitiesService = Depends(get_entities_service),
) -> EntityRead:
    updated = service.update_entity(entity_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found",
        )
    return updated


@router.delete(
    "/{entity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an entity",
    description="Delete a saved entity. Used by the Architect workspace UI.",
)
def delete_entity(
    *,
    entity_id: int,
    service: EntitiesService = Depends(get_entities_service),
) -> None:
    deleted = service.delete_entity(entity_id)
    if not deleted:
        # You can change this to silently return 204 if you prefer fully idempotent deletes.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found",
        )
