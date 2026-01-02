# app/core/ports/task_queue.py
from __future__ import annotations

from typing import Mapping, Optional, Protocol


class ITaskQueue(Protocol):
    """
    Port for background job enqueueing (task queue).

    This is NOT the pub/sub event bus (IMessageBroker).
    """

    async def enqueue_language_build(
        self,
        *,
        lang_code: str,
        strategy: str = "fast",
        correlation_id: Optional[str] = None,
        trace_context: Optional[Mapping[str, str]] = None,
    ) -> str:
        """Enqueue a build job and return the job id."""
        ...

    async def connect(self) -> None:
        """Optional: initialize underlying connections/pools."""
        ...

    async def disconnect(self) -> None:
        """Optional: close underlying connections/pools."""
        ...

    async def health_check(self) -> bool:
        """Return True iff the queue backend is reachable."""
        ...