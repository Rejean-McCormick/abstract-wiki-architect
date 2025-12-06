# architect_http_api/repositories/generations.py

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from architect_http_api.db.models import Generation


__all__ = ["GenerationsRepository", "generations_repository"]


class GenerationsRepository:
    """
    Repository for persisting and querying text/frame generations.

    This is intentionally thin: it works directly with the SQLAlchemy ORM
    model `Generation` and simple Python primitives. Higher-level concerns
    (validation, Pydantic schemas, business logic) live in the service layer.
    """

    # ------------------------------------------------------------------
    # Create / update
    # ------------------------------------------------------------------

    def create_pending(
        self,
        db: Session,
        *,
        frame_slug: str,
        language_code: Optional[str],
        intent: Optional[str],
        request_payload: Dict[str, Any],
        source: Optional[str] = None,
    ) -> Generation:
        """
        Insert a new 'pending' generation row before calling the NLG engine.

        This lets us keep a record even if the downstream call fails.
        """
        generation = Generation(
            frame_slug=frame_slug,
            language_code=language_code,
            intent=intent,
            status="pending",
            request_payload=request_payload,
            response_payload=None,
            error_message=None,
            source=source,
        )
        db.add(generation)
        db.commit()
        db.refresh(generation)
        return generation

    def mark_success(
        self,
        db: Session,
        generation: Generation,
        *,
        response_payload: Dict[str, Any],
    ) -> Generation:
        """
        Mark a previously pending generation as successfully completed.
        """
        generation.status = "success"
        generation.response_payload = response_payload
        generation.error_message = None

        db.add(generation)
        db.commit()
        db.refresh(generation)
        return generation

    def mark_failure(
        self,
        db: Session,
        generation: Generation,
        *,
        error_message: str,
        response_payload: Optional[Dict[str, Any]] = None,
    ) -> Generation:
        """
        Mark a previously pending generation as failed.

        Optionally attach any partial response payload (for debugging).
        """
        generation.status = "failed"
        generation.error_message = error_message
        if response_payload is not None:
            generation.response_payload = response_payload

        db.add(generation)
        db.commit()
        db.refresh(generation)
        return generation

    # ------------------------------------------------------------------
    # Fetch
    # ------------------------------------------------------------------

    def get_by_id(self, db: Session, generation_id: int) -> Optional[Generation]:
        """
        Fetch a single generation by primary key.
        """
        return db.get(Generation, generation_id)

    def list_recent(
        self,
        db: Session,
        *,
        frame_slug: Optional[str] = None,
        language_code: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20,
    ) -> List[Generation]:
        """
        List recent generations, optionally filtered by frame, language, and status.
        Ordered newest-first.
        """
        stmt = select(Generation)

        if frame_slug is not None:
            stmt = stmt.where(Generation.frame_slug == frame_slug)
        if language_code is not None:
            stmt = stmt.where(Generation.language_code == language_code)
        if status is not None:
            stmt = stmt.where(Generation.status == status)

        stmt = stmt.order_by(desc(Generation.created_at)).limit(limit)

        result = db.execute(stmt)
        return list(result.scalars().all())

    def list_for_frame(
        self,
        db: Session,
        *,
        frame_slug: str,
        limit: int = 50,
    ) -> List[Generation]:
        """
        Convenience wrapper: recent generations for a single frame slug.
        """
        return self.list_recent(db, frame_slug=frame_slug, limit=limit)


generations_repository = GenerationsRepository()
