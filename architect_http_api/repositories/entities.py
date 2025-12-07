# architect_http_api/repositories/entities.py

from __future__ import annotations

from typing import Any, Iterable, Optional, Sequence, Union
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from ..db import models


EntityId = Union[int, UUID]


class EntitiesRepository:
    """
    Thin data-access layer around the Entity model.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @property
    def session(self) -> Session:
        return self._session

    def _base_select(self) -> Select[Any]:
        return select(models.Entity)

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def list_entities(
        self,
        *,
        frame_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[models.Entity]:
        """
        Return a paginated list of entities.
        
        Note: Filtering by 'frame_type' is handled in the Service layer (Python side)
        because 'frame_type' is stored inside the JSON 'data' blob, not as a SQL column.
        """
        stmt = self._base_select()

        # Prefer most recently touched entities first.
        stmt = stmt.order_by(
            models.Entity.updated_at.desc().nullslast(),
            models.Entity.created_at.desc(),
        )

        if offset:
            stmt = stmt.offset(offset)
        if limit:
            stmt = stmt.limit(limit)

        result = self.session.execute(stmt)
        return list(result.scalars().all())

    def get_by_id(self, entity_id: EntityId) -> Optional[models.Entity]:
        """
        Fetch a single entity by primary key, or None if it does not exist.
        """
        return self.session.get(models.Entity, entity_id)

    def get_by_slug(self, slug: str) -> Optional[models.Entity]:
        """
        Fetch a single entity by its slug, or None if it does not exist.
        """
        stmt = self._base_select().where(models.Entity.slug == slug)
        result = self.session.execute(stmt)
        return result.scalar_one_or_none()

    def search(
        self,
        query: str,
        *,
        frame_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[models.Entity]:
        """
        Simple case-insensitive text search over name and slug.
        """
        pattern = f"%{query.lower()}%"

        # Fixed: Use 'name' instead of 'title' (column mismatch)
        stmt = self._base_select().where(
            func.or_(
                func.lower(models.Entity.name).like(pattern),
                func.lower(models.Entity.slug).like(pattern),
            )
        )

        stmt = stmt.order_by(
            models.Entity.updated_at.desc().nullslast(),
            models.Entity.created_at.desc(),
        )

        if offset:
            stmt = stmt.offset(offset)
        if limit:
            stmt = stmt.limit(limit)

        result = self.session.execute(stmt)
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def create(
        self,
        *,
        slug: str,
        frame_type: str,
        title: str,
        data: dict[str, Any],
        metadata: Optional[dict[str, Any]] = None,
    ) -> models.Entity:
        """
        Create and persist a new Entity.
        """
        # Fixed: Inject frame_type into data since there is no frame_type column
        final_data = data.copy() if data else {}
        final_data["frame_type"] = frame_type

        # Fixed: Use 'name' instead of 'title' for the model field
        entity = models.Entity(
            slug=slug,
            name=title, 
            data=final_data,
            # tags or metadata can be stored in the 'tags' column if needed,
            # or in 'data' depending on your model structure. 
            # Assuming 'tags' column is JSON based on previous dumps:
            tags=metadata or {}, 
        )

        self.session.add(entity)
        self.session.flush()

        return entity

    def update(
        self,
        entity: models.Entity,
        *,
        title: Optional[str] = None,
        frame_type: Optional[str] = None,
        data: Optional[dict[str, Any]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> models.Entity:
        """
        Apply partial updates to an existing Entity and flush.
        """
        if title is not None:
            entity.name = title  # Fixed: 'name' not 'title'
        
        # If updating data or frame_type, we need to handle the JSON blob
        if data is not None or frame_type is not None:
            current_data = dict(entity.data) if entity.data else {}
            
            if data is not None:
                current_data.update(data)
            
            if frame_type is not None:
                current_data["frame_type"] = frame_type
                
            entity.data = current_data

        if metadata is not None:
            entity.tags = metadata # Assuming metadata maps to tags column

        self.session.add(entity)
        self.session.flush()

        return entity

    def update_fields(
        self,
        entity_id: EntityId,
        *,
        fields: dict[str, Any],
    ) -> Optional[models.Entity]:
        """
        Convenience method: load an entity by id, apply the given field updates,
        and flush. Returns the updated entity, or None if it does not exist.
        """
        entity = self.get_by_id(entity_id)
        if entity is None:
            return None

        for key, value in fields.items():
            if key == 'title': # specific fix for mismatched keys
                setattr(entity, 'name', value)
            elif key == 'data' and isinstance(value, dict):
                # Ensure we don't lose frame_type if it's already there
                current = dict(entity.data or {})
                current.update(value)
                entity.data = current
            elif hasattr(entity, key):
                setattr(entity, key, value)

        self.session.add(entity)
        self.session.flush()

        return entity

    def delete(self, entity: models.Entity) -> None:
        """
        Delete an entity instance.
        """
        self.session.delete(entity)
        self.session.flush()

    def delete_by_id(self, entity_id: EntityId) -> bool:
        """
        Delete an entity by id. Returns True if an entity was deleted.
        """
        entity = self.get_by_id(entity_id)
        if entity is None:
            return False

        self.session.delete(entity)
        self.session.flush()
        return True

    # ------------------------------------------------------------------
    # Bulk utilities
    # ------------------------------------------------------------------

    def bulk_get_by_ids(
        self,
        ids: Iterable[EntityId],
    ) -> Sequence[models.Entity]:
        """
        Fetch multiple entities by id in one query.
        """
        ids_list = list(ids)
        if not ids_list:
            return []

        stmt = self._base_select().where(models.Entity.id.in_(ids_list))  # type: ignore[attr-defined]
        result = self.session.execute(stmt)
        return list(result.scalars().all())