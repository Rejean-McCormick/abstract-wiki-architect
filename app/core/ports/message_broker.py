# app/core/ports/message_broker.py
from __future__ import annotations

from typing import Awaitable, Callable, Protocol

from app.core.domain.events import EventType, SystemEvent

EventHandler = Callable[[SystemEvent], Awaitable[None]]


class IMessageBroker(Protocol):
    """
    Port for the Domain Event Bus (publish/subscribe).

    Notes:
    - This port is for *events* (pub/sub semantics).
    - Do NOT overload it with *job queue* semantics (ARQ/Celery enqueue).
      Model queues via a separate port (e.g., ITaskQueue) to avoid split-brain failures.
    """

    async def connect(self) -> None:
        """Open underlying connection(s) (called on service startup)."""
        ...

    async def disconnect(self) -> None:
        """Close underlying connection(s) and stop background listeners."""
        ...

    async def publish(self, event: SystemEvent) -> None:
        """Publish a domain event to the bus."""
        ...

    async def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """
        Register a handler to run when a specific domain event type is received.

        Implementations should ensure handler exceptions do not crash the listener loop.
        """
        ...

    async def health_check(self) -> bool:
        """Return True iff the broker is connected and reachable."""
        ...
