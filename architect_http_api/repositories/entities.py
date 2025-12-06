


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

    This class is intentionally small and synchronous; transaction / commit
    handling is the responsibility of the caller (typically the FastAPI
    dependency that manages a per-request SQLAlchemy Session).

    Typical usage:

        repo = EntitiesRepository(session)
        entities = repo.list_entities(limit=20)
        entity = repo.get_by_slug("marie-curie")
        new_entity = repo.create(
            slug="marie-curie",
            frame_type="PERSON",
            title="Marie Curie",
            data={...},
        )
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
        Return a paginated list of entities, optionally filtered by frame_type.

        Results are ordered by updated_at (desc), then created_at (desc).
        """
        stmt = self._base_select()

        if frame_type:
            stmt = stmt.where(models.Entity.frame_type == frame_type)

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
        Simple case-insensitive text search over title and slug.

        This is intentionally minimal; callers can layer more advanced search
        capabilities on top if needed.
        """
        pattern = f"%{query.lower()}%"

        stmt = self._base_select().where(
            func.or_(
                func.lower(models.Entity.title).like(pattern),
                func.lower(models.Entity.slug).like(pattern),
            )
        )

        if frame_type:
            stmt = stmt.where(models.Entity.frame_type == frame_type)

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

        The caller is responsible for committing the transaction.
        """
        entity = models.Entity(
            slug=slug,
            frame_type=frame_type,
            title=title,
            data=data,
            metadata=metadata or {},
        )

        self.session.add(entity)
        # Flush so that PK and timestamps are populated before returning.
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

        The provided `entity` instance must be attached to the current Session.
        """
        if title is not None:
            entity.title = title
        if frame_type is not None:
            entity.frame_type = frame_type
        if data is not None:
            entity.data = data
        if metadata is not None:
            entity.metadata = metadata

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
            if hasattr(entity, key):
                setattr(entity, key, value)

        self.session.add(entity)
        self.session.flush()

        return entity

    def delete(self, entity: models.Entity) -> None:
        """
        Delete an entity instance.

        The caller is responsible for committing the transaction.
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

        The return order is database-defined (not guaranteed to match `ids`).
        """
        ids_list = list(ids)
        if not ids_list:
            return []

        stmt = self._base_select().where(models.Entity.id.in_(ids_list))  # type: ignore[attr-defined]
        result = self.session.execute(stmt)
        return list(result.scalars().all())
