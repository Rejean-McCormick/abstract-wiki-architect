# architect_http_api/repositories/logs.py

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Iterable, Optional

from sqlalchemy.orm import Session

from architect_http_api.db.models import LogEntry


class LogsRepository:
    """
    Persistence layer for request / generation logs.

    This repository is intentionally generic so it can be reused for:
    - HTTP request logs
    - frame-generation traces
    - AI-assistant interactions, etc.

    It expects a `LogEntry` ORM model with (at least) the following fields:

        id: int (PK)
        created_at: datetime
        level: str
        event_type: str
        message: Optional[str]
        request_id: Optional[str]
        frame_type: Optional[str]
        frame_slug: Optional[str]
        lang: Optional[str]
        status: Optional[str]
        latency_ms: Optional[int]
        payload: Optional[dict]
        result: Optional[dict]
        error: Optional[dict]
        metadata: Optional[dict]

    If you adjust the model, keep the field names used below in sync.
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    # -------------------------------------------------------------------------
    # Basic CRUD
    # -------------------------------------------------------------------------

    def get(self, log_id: int) -> Optional[LogEntry]:
        """Return a single log entry by primary key, or None if not found."""
        return self._db.get(LogEntry, log_id)

    def list_recent(
        self,
        *,
        limit: int = 100,
        event_type: Optional[str] = None,
        request_id: Optional[str] = None,
        frame_type: Optional[str] = None,
        level: Optional[str] = None,
    ) -> list[LogEntry]:
        """
        Fetch recent log entries with optional filters.

        Results are ordered by `created_at` descending.
        """
        query = self._db.query(LogEntry)

        if event_type is not None:
            query = query.filter(LogEntry.event_type == event_type)
        if request_id is not None:
            query = query.filter(LogEntry.request_id == request_id)
        if frame_type is not None:
            query = query.filter(LogEntry.frame_type == frame_type)
        if level is not None:
            query = query.filter(LogEntry.level == level)

        return (
            query.order_by(LogEntry.created_at.desc())
            .limit(max(limit, 1))
            .all()
        )

    def create(
        self,
        *,
        level: str,
        event_type: str,
        message: Optional[str] = None,
        request_id: Optional[str] = None,
        frame_type: Optional[str] = None,
        frame_slug: Optional[str] = None,
        lang: Optional[str] = None,
        status: Optional[str] = None,
        latency_ms: Optional[int] = None,
        payload: Optional[Mapping[str, Any]] = None,
        result: Optional[Mapping[str, Any]] = None,
        error: Optional[Mapping[str, Any]] = None,
        metadata: Optional[Mapping[str, Any]] = None,
        commit: bool = True,
    ) -> LogEntry:
        """
        Insert a generic log entry.

        This is the low-level primitive used by higher-level helpers like
        `log_generation_event`.
        """
        entry = LogEntry(
            level=level,
            event_type=event_type,
            message=message,
            request_id=request_id,
            frame_type=frame_type,
            frame_slug=frame_slug,
            lang=lang,
            status=status,
            latency_ms=latency_ms,
            payload=dict(payload) if payload is not None else None,
            result=dict(result) if result is not None else None,
            error=dict(error) if error is not None else None,
            metadata=dict(metadata) if metadata is not None else None,
        )

        self._db.add(entry)

        if commit:
            self._db.commit()
            self._db.refresh(entry)

        return entry

    def create_many(
        self,
        entries: Iterable[LogEntry],
        *,
        commit: bool = True,
    ) -> None:
        """
        Bulk-insert already-constructed `LogEntry` instances.

        Useful for batch import / migration tasks.
        """
        self._db.add_all(list(entries))

        if commit:
            self._db.commit()

    # -------------------------------------------------------------------------
    # Domain-specific helpers
    # -------------------------------------------------------------------------

    def log_generation_event(
        self,
        *,
        request_id: Optional[str],
        frame_type: Optional[str],
        frame_slug: Optional[str],
        lang: Optional[str],
        status: str,
        payload: Optional[Mapping[str, Any]] = None,
        result: Optional[Mapping[str, Any]] = None,
        error_message: Optional[str] = None,
        error_detail: Optional[Mapping[str, Any]] = None,
        latency_ms: Optional[int] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> LogEntry:
        """
        Convenience helper for logging a generation request/response pair.

        `status` is typically "ok" / "error".
        """
        level = "error" if status.lower() == "error" else "info"

        error: Optional[dict[str, Any]]
        if error_message or error_detail:
            error = {
                "message": error_message,
                "detail": dict(error_detail) if error_detail is not None else None,
            }
        else:
            error = None

        message = error_message or "generation"

        return self.create(
            level=level,
            event_type="generation",
            message=message,
            request_id=request_id,
            frame_type=frame_type,
            frame_slug=frame_slug,
            lang=lang,
            status=status,
            latency_ms=latency_ms,
            payload=payload,
            result=result,
            error=error,
            metadata=metadata,
        )
