# app/adapters/task_queue.py
from __future__ import annotations

import inspect
from typing import Any, Dict, Mapping, Optional

import structlog
from arq.connections import RedisSettings, create_pool

from app.core.ports.task_queue import ITaskQueue
from app.shared.config import settings

logger = structlog.get_logger()


class ArqTaskQueue(ITaskQueue):
    """
    ARQ-backed task queue adapter.

    Worker registers functions like:
      - build_language(ctx, request_dict)
    and listens on settings.REDIS_QUEUE_NAME.
    """

    def __init__(
        self,
        redis_dsn: str = settings.REDIS_URL,
        queue_name: str = settings.REDIS_QUEUE_NAME,
    ) -> None:
        self._redis_dsn = redis_dsn
        self._queue_name = queue_name
        self._redis = None  # created lazily

    async def connect(self) -> None:
        if self._redis is not None:
            return
        self._redis = await create_pool(RedisSettings.from_dsn(self._redis_dsn))
        # Fail fast if redis is unreachable
        try:
            await self._redis.ping()
        except Exception:
            await self.disconnect()
            raise

    async def disconnect(self) -> None:
        if self._redis is None:
            return

        r = self._redis
        self._redis = None

        # Be defensive across arq/redis-py versions
        close = getattr(r, "close", None)
        if callable(close):
            res = close()
            if inspect.isawaitable(res):
                await res

        wait_closed = getattr(r, "wait_closed", None)
        if callable(wait_closed):
            res = wait_closed()
            if inspect.isawaitable(res):
                await res

        # Some versions require disconnecting the connection pool
        pool = getattr(r, "connection_pool", None)
        disc = getattr(pool, "disconnect", None) if pool is not None else None
        if callable(disc):
            res = disc()
            if inspect.isawaitable(res):
                await res

    async def health_check(self) -> bool:
        try:
            if self._redis is None:
                await self.connect()
            return bool(await self._redis.ping())
        except Exception:
            return False

    async def enqueue_language_build(
        self,
        *,
        lang_code: str,
        strategy: str = "fast",
        correlation_id: Optional[str] = None,
        trace_context: Optional[Mapping[str, str]] = None,
    ) -> str:
        if self._redis is None:
            await self.connect()

        request: Dict[str, Any] = {
            "lang_code": lang_code,
            "strategy": strategy,
        }

        # These extras are useful for tracing/dedupe; worker payload model should ignore extras.
        if correlation_id:
            request["correlation_id"] = correlation_id
        if trace_context:
            request["trace_context"] = dict(trace_context)

        job = await self._redis.enqueue_job(
            "build_language",
            request,
            _queue_name=self._queue_name,
            _job_id=correlation_id,  # safe: BuildLanguage uses a fresh UUID event.id
        )

        # ARQ returns a Job object; normalize to str
        job_id = getattr(job, "job_id", None)
        return str(job_id if job_id is not None else job)