# architect_http_api/repositories/frames.py

from __future__ import annotations

from typing import Iterable, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from architect_http_api.db.models import FrameModel


class FramesRepository:
    """
    Persistence layer for UI frames / frame presets.

    This repository is intentionally minimal. It assumes a SQLAlchemy
    `FrameModel` with (at least) the following columns:

        - id: int (PK)
        - slug: str (unique, stable identifier like "entity.person" or "bio.simple")
        - title: str
        - family: str | None (e.g. "entity", "event", "narrative", ...)
        - description: str | None
        - schema: JSON | None   (frame payload schema / example structure)
        - ui_hints: JSON | None (frontend-specific hints such as grouping, icons, etc.)
        - created_at / updated_at: timestamps (optional but recommended)

    The service layer is responsible for mapping between `FrameModel` instances
    and Pydantic schemas defined in `architect_http_api.schemas.frames_metadata`.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Basic retrieval
    # ------------------------------------------------------------------

    def get(self, frame_id: int) -> Optional[FrameModel]:
        """
        Return a frame by numeric id, or None if it does not exist.
        """
        return self._session.get(FrameModel, frame_id)

    def get_by_slug(self, slug: str) -> Optional[FrameModel]:
        """
        Return a frame by its canonical slug, or None if not found.
        """
        stmt = select(FrameModel).where(FrameModel.slug == slug)
        return self._session.scalar(stmt)

    def list_all(self) -> List[FrameModel]:
        """
        Return all frames (typically a small catalogue).
        """
        stmt = select(FrameModel).order_by(FrameModel.slug)
        return list(self._session.scalars(stmt))

    # ------------------------------------------------------------------
    # Creation / update
    # ------------------------------------------------------------------

    def create(
        self,
        *,
        slug: str,
        title: str,
        family: Optional[str] = None,
        description: Optional[str] = None,
        schema: Optional[dict] = None,
        ui_hints: Optional[dict] = None,
    ) -> FrameModel:
        """
        Create a new frame row.

        If a frame with the same slug already exists, this will raise
        an IntegrityError when the transaction is committed (assuming a
        UNIQUE constraint on `slug`).
        """
        frame = FrameModel(
            slug=slug,
            title=title,
            family=family,
            description=description,
            schema=schema or {},
            ui_hints=ui_hints or {},
        )
        self._session.add(frame)
        self._session.flush()  # populate `id` from the database
        return frame

    def update(
        self,
        frame: FrameModel,
        *,
        title: Optional[str] = None,
        family: Optional[str] = None,
        description: Optional[str] = None,
        schema: Optional[dict] = None,
        ui_hints: Optional[dict] = None,
    ) -> FrameModel:
        """
        Update fields on an existing frame.

        Only non-None keyword arguments are applied.
        """
        if title is not None:
            frame.title = title
        if family is not None:
            frame.family = family
        if description is not None:
            frame.description = description
        if schema is not None:
            frame.schema = schema
        if ui_hints is not None:
            frame.ui_hints = ui_hints

        self._session.flush()
        return frame

    def upsert(
        self,
        *,
        slug: str,
        title: str,
        family: Optional[str] = None,
        description: Optional[str] = None,
        schema: Optional[dict] = None,
        ui_hints: Optional[dict] = None,
    ) -> FrameModel:
        """
        Convenience helper: create or update a frame identified by `slug`.

        This is useful when synchronizing the static `frames_registry`
        catalogue into the database.
        """
        existing = self.get_by_slug(slug)
        if existing is None:
            return self.create(
                slug=slug,
                title=title,
                family=family,
                description=description,
                schema=schema,
                ui_hints=ui_hints,
            )

        return self.update(
            existing,
            title=title,
            family=family,
            description=description,
            schema=schema,
            ui_hints=ui_hints,
        )

    # ------------------------------------------------------------------
    # Deletion
    # ------------------------------------------------------------------

    def delete(self, frame: FrameModel) -> None:
        """
        Delete a frame instance.
        """
        self._session.delete(frame)
        # Caller is responsible for committing.

    def delete_by_slug(self, slug: str) -> int:
        """
        Delete a frame by slug.

        Returns the number of rows deleted (0 or 1).
        """
        frame = self.get_by_slug(slug)
        if frame is None:
            return 0
        self._session.delete(frame)
        return 1

    # ------------------------------------------------------------------
    # Bulk helpers
    # ------------------------------------------------------------------

    def bulk_upsert_from_registry(
        self,
        items: Iterable[dict],
        *,
        slug_key: str = "slug",
        title_key: str = "title",
        family_key: str = "family",
        description_key: str = "description",
        schema_key: str = "schema",
        ui_hints_key: str = "ui_hints",
    ) -> List[FrameModel]:
        """
        Optional helper to synchronize a registry catalogue into the DB.

        `items` is expected to be an iterable of plain dicts (e.g. serialized
        Pydantic models from `frames_metadata`). Key names are customizable
        via the `*_key` parameters.
        """
        results: List[FrameModel] = []
        for item in items:
            slug = item[slug_key]
            title = item[title_key]
            family = item.get(family_key)
            description = item.get(description_key)
            schema = item.get(schema_key)
            ui_hints = item.get(ui_hints_key)

            frame = self.upsert(
                slug=slug,
                title=title,
                family=family,
                description=description,
                schema=schema,
                ui_hints=ui_hints,
            )
            results.append(frame)

        return results
