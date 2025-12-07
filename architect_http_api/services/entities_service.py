# architect_http_api/services/entities_service.py

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

    def create_entity(self, payload: EntityCreate) -> EntityRead:
        """
        Create a new entity.
        Enforces slug uniqueness.
        """
        # 1. Determine Slug
        slug = payload.slug
        if not slug:
            # Simple auto-generation
            slug = payload.name.lower().replace(" ", "-")

        # 2. Check Uniqueness
        existing = self._repo.get_by_slug(slug)
        if existing is not None:
            raise DuplicateEntitySlugError(slug)

        # 3. Create in DB
        # Note: We map Pydantic fields to the Repository arguments here
        entity = self._repo.create(
            slug=slug,
            frame_type=payload.frame_type or "generic",
            title=payload.name,  # Mapping 'name' schema field to 'title' repo arg/column
            data=payload.frame_payload or {},
            metadata=payload.metadata
        )
        
        # 4. Commit transaction
        self._repo.session.commit()
        
        return EntityRead.from_orm(entity)

    def get_entity(self, entity_id: int) -> EntityRead:
        """
        Retrieve a single entity by numeric ID.
        """
        entity = self._repo.get_by_id(entity_id)
        if entity is None:
            raise EntityNotFoundError(f"Entity with id={entity_id} not found.")
        return EntityRead.from_orm(entity)

    def get_entity_by_slug(self, slug: str) -> EntityRead:
        """
        Retrieve a single entity by slug.
        """
        entity = self._repo.get_by_slug(slug)
        if entity is None:
            raise EntityNotFoundError(f"Entity with slug='{slug}' not found.")
        return EntityRead.from_orm(entity)

    def list_entities(
        self,
        *,
        search: Optional[str] = None,
        frame_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[EntityRead]:
        """
        List entities with optional search and pagination.
        """
        if search:
            entities = self._repo.search(
                query=search, 
                frame_type=frame_type, 
                limit=limit, 
                offset=offset
            )
        else:
            entities = self._repo.list_entities(
                frame_type=frame_type, 
                limit=limit, 
                offset=offset
            )
            
        return [EntityRead.from_orm(e) for e in entities]

    def update_entity(self, entity_id: int, payload: EntityUpdate) -> EntityRead:
        """
        Update an existing entity.
        """
        entity = self._repo.get_by_id(entity_id)
        if entity is None:
            raise EntityNotFoundError(f"Entity with id={entity_id} not found.")

        # Check slug uniqueness if changing
        if payload.slug and payload.slug != entity.slug:
            existing = self._repo.get_by_slug(payload.slug)
            if existing is not None and existing.id != entity_id:
                raise DuplicateEntitySlugError(payload.slug)

        # Build update dictionary
        updates = {}
        if payload.name is not None:
            updates["title"] = payload.name  # Map schema 'name' to DB 'title'
        if payload.slug is not None:
            updates["slug"] = payload.slug
        if payload.frame_type is not None:
            updates["frame_type"] = payload.frame_type
        if payload.frame_payload is not None:
            updates["data"] = payload.frame_payload
        if payload.metadata is not None:
            updates["metadata"] = payload.metadata

        if updates:
            self._repo.update_fields(entity_id, fields=updates)
            self._repo.session.commit()
            # Refresh to get updated object
            entity = self._repo.get_by_id(entity_id)

        return EntityRead.from_orm(entity)

    def delete_entity(self, entity_id: int) -> bool:
        """
        Delete an entity by ID.
        """
        deleted = self._repo.delete_by_id(entity_id)
        if not deleted:
            # Depending on preference, raise error or return False
            # Here we follow the requested interface to return False or raise
            return False
        
        self._repo.session.commit()
        return True