from __future__ import annotations

from typing import List, Optional

from architect_http_api.repositories.entities import EntitiesRepository
from architect_http_api.schemas.entities import EntityCreate, EntityUpdate, EntityRead


class EntityNotFoundError(Exception):
    """Raised when an entity cannot be found in the repository."""


class DuplicateEntitySlugError(Exception):
    """Raised when trying to create/update an entity with a slug that already exists."""

    def __init__(self, slug: str) -> None:
        super().__init__(f"Entity with slug '{slug}' already exists.")
        self.slug = slug


class EntitiesService:
    """
    High-level service for working with Architect entities.

    Responsibilities:
    - Enforce simple business rules (slug uniqueness, existence checks).
    - Delegate persistence to `EntitiesRepository`.
    - Convert repository models to API schemas (`EntityRead`).
    """

    def __init__(self, repo: EntitiesRepository) -> None:
        self._repo = repo

    # -------------------------------------------------------------------------
    # Core CRUD operations
    # -------------------------------------------------------------------------

    async def create_entity(self, payload: EntityCreate) -> EntityRead:
        """
        Create a new entity.

        Enforces:
        - Slug uniqueness, if `payload.slug` is provided.
        """
        if payload.slug:
            existing = await self._repo.get_by_slug(payload.slug)
            if existing is not None:
                raise DuplicateEntitySlugError(payload.slug)

        entity = await self._repo.create(payload)
        return EntityRead.from_orm(entity)

    async def get_entity(self, entity_id: int) -> EntityRead:
        """
        Retrieve a single entity by numeric ID.
        """
        entity = await self._repo.get_by_id(entity_id)
        if entity is None:
            raise EntityNotFoundError(f"Entity with id={entity_id} not found.")
        return EntityRead.from_orm(entity)

    async def get_entity_by_slug(self, slug: str) -> EntityRead:
        """
        Retrieve a single entity by slug.
        """
        entity = await self._repo.get_by_slug(slug)
        if entity is None:
            raise EntityNotFoundError(f"Entity with slug='{slug}' not found.")
        return EntityRead.from_orm(entity)

    async def list_entities(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> List[EntityRead]:
        """
        List entities with simple pagination.
        """
        entities = await self._repo.list(limit=limit, offset=offset)
        return [EntityRead.from_orm(e) for e in entities]

    async def update_entity(self, entity_id: int, payload: EntityUpdate) -> EntityRead:
        """
        Update an existing entity.

        Enforces:
        - Slug uniqueness, if `payload.slug` is set and different from the current one.
        """
        # If a slug is being set/changed, make sure it's unique.
        if payload.slug:
            existing = await self._repo.get_by_slug(payload.slug)
            if existing is not None and getattr(existing, "id", None) != entity_id:
                raise DuplicateEntitySlugError(payload.slug)

        updated = await self._repo.update(entity_id, payload)
        if updated is None:
            raise EntityNotFoundError(f"Entity with id={entity_id} not found.")

        return EntityRead.from_orm(updated)

    async def delete_entity(self, entity_id: int) -> None:
        """
        Delete an entity by ID.

        The underlying repository is expected to return:
        - True if a row was deleted.
        - False if nothing matched.
        """
        deleted = await self._repo.delete(entity_id)
        if not deleted:
            raise EntityNotFoundError(f"Entity with id={entity_id} not found.")
