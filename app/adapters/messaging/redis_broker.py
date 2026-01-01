# app/adapters/messaging/redis_broker.py
import asyncio
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional

import redis.asyncio as redis
import structlog

from app.core.domain.events import SystemEvent
from app.core.ports.message_broker import IMessageBroker
from app.shared.config import settings

logger = structlog.get_logger()


def _channel_name(event_type: Any) -> str:
    """
    Normalize EventType inputs to a Redis channel name.

    Critical: Enum(str) prints as 'EventType.X' with str(enum_member),
    so we MUST use .value.
    """
    if isinstance(event_type, Enum):
        return str(event_type.value)
    return str(event_type)


def _ensure_str(v: Any) -> str:
    if isinstance(v, bytes):
        return v.decode("utf-8", errors="replace")
    return str(v)


class RedisMessageBroker(IMessageBroker):
    """
    Concrete implementation of the Message Broker using Redis Pub/Sub.

    NOTE: Pub/Sub is ephemeral (not a durable job queue). If you need ARQ execution,
    a separate bridge should translate events -> enqueue_job(...).
    """

    def __init__(self) -> None:
        self.redis_url = settings.REDIS_URL

        self._client: Optional[redis.Redis] = None
        self._pubsub: Optional[redis.client.PubSub] = None

        # Registry of local handlers: { "channel": [handler_func, ...] }
        self._handlers: Dict[str, List[Callable[[SystemEvent], Coroutine[Any, Any, None]]]] = {}

        self._listener_task: Optional[asyncio.Task] = None
        self._connect_lock = asyncio.Lock()

    async def connect(self) -> None:
        """Explicit connection start (called on app startup)."""
        async with self._connect_lock:
            if self._client:
                return

            self._client = redis.from_url(self.redis_url, decode_responses=True)

            # Ignore subscribe/unsubscribe control messages; only yield real messages.
            self._pubsub = self._client.pubsub(ignore_subscribe_messages=True)

            # Fail fast if Redis is unreachable
            await self._client.ping()
            logger.info("redis_broker_connected", redis_url=self.redis_url)

    async def disconnect(self) -> None:
        """Clean shutdown."""
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
            finally:
                self._listener_task = None

        if self._pubsub:
            try:
                await self._pubsub.close()
            finally:
                self._pubsub = None

        if self._client:
            try:
                await self._client.close()
            finally:
                self._client = None

        logger.info("redis_broker_disconnected")

    async def publish(self, event: SystemEvent) -> None:
        """
        Publishes an event to a Redis channel named after the event type.
        """
        if not self._client:
            await self.connect()
        assert self._client is not None

        channel = _channel_name(event.type)

        try:
            message_body = event.model_dump_json()
            await self._client.publish(channel, message_body)
            logger.debug("event_published", channel=channel, type=str(event.type), id=event.id)
        except Exception as e:
            logger.error("redis_publish_failed", error=str(e), event_id=event.id, channel=channel)
            raise

    async def subscribe(
        self,
        event_type: str,
        handler: Callable[[SystemEvent], Coroutine[Any, Any, None]],
    ) -> None:
        """
        Registers a local handler and subscribes to the Redis channel.
        """
        if not self._client or not self._pubsub:
            await self.connect()
        assert self._pubsub is not None

        channel = _channel_name(event_type)

        if channel not in self._handlers:
            self._handlers[channel] = []
            await self._pubsub.subscribe(channel)

        self._handlers[channel].append(handler)
        logger.info("handler_registered", channel=channel)

        if not self._listener_task or self._listener_task.done():
            self._listener_task = asyncio.create_task(self._listen_loop())

    async def _listen_loop(self) -> None:
        """
        Continuous loop that pulls messages from Redis and dispatches them.
        """
        assert self._pubsub is not None

        logger.info("redis_listener_loop_started")
        try:
            async for message in self._pubsub.listen():
                # with ignore_subscribe_messages=True, we only receive actual messages here
                await self._process_message(message)
        except asyncio.CancelledError:
            logger.info("redis_listener_cancelled")
        except Exception as e:
            logger.error("redis_listener_crashed", error=str(e))

    async def _process_message(self, raw_msg: Dict[str, Any]) -> None:
        """
        Deserializes the Redis message and invokes registered handlers.
        """
        channel = _ensure_str(raw_msg.get("channel"))
        data = raw_msg.get("data")

        try:
            if isinstance(data, bytes):
                data = data.decode("utf-8", errors="replace")

            # Pydantic v2 fast path
            if hasattr(SystemEvent, "model_validate_json") and isinstance(data, str):
                event = SystemEvent.model_validate_json(data)  # type: ignore[attr-defined]
            else:
                # Fallback: parse via dict
                import json

                payload_dict = json.loads(data)
                event = SystemEvent(**payload_dict)

            handlers = self._handlers.get(channel, [])
            if not handlers:
                logger.debug("event_received_no_handlers", channel=channel, event_id=getattr(event, "id", None))
                return

            for handler in handlers:
                try:
                    await handler(event)
                except Exception as handler_err:
                    logger.error("event_handler_failed", channel=channel, error=str(handler_err), event_id=event.id)

        except Exception as e:
            logger.error("message_deserialization_failed", channel=channel, error=str(e))

    async def health_check(self) -> bool:
        if not self._client:
            return False
        try:
            return bool(await self._client.ping())
        except Exception:
            return False
