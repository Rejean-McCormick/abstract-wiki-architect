# app\adapters\messaging\redis_broker.py
import asyncio
import json
import redis.asyncio as redis
from typing import Callable, Coroutine, Dict, List, Any, Optional
import structlog

from app.core.ports.message_broker import IMessageBroker
from app.core.domain.events import SystemEvent
from app.shared.config import settings

logger = structlog.get_logger()

class RedisMessageBroker(IMessageBroker):
    """
    Concrete implementation of the Message Broker using Redis Pub/Sub.
    """

    def __init__(self):
        self.redis_url = settings.REDIS_URL
        self._client: Optional[redis.Redis] = None
        self._pubsub: Optional[redis.client.PubSub] = None
        
        # Registry of local handlers: { 'event.type': [handler_func, ...] }
        self._handlers: Dict[str, List[Callable[[SystemEvent], Coroutine[Any, Any, None]]]] = {}
        
        # Background task for reading messages
        self._listener_task: Optional[asyncio.Task] = None

    async def connect(self):
        """Explicit connection start (called on app startup)."""
        if not self._client:
            self._client = redis.from_url(self.redis_url, decode_responses=True)
            self._pubsub = self._client.pubsub()
            logger.info("redis_broker_connected")

    async def disconnect(self):
        """Clean shutdown."""
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
        
        if self._pubsub:
            await self._pubsub.close()
        
        if self._client:
            await self._client.close()
            
        logger.info("redis_broker_disconnected")

    async def publish(self, event: SystemEvent) -> None:
        """
        Publishes an event to a Redis channel named after the event type.
        """
        if not self._client:
            await self.connect()

        try:
            # We serialize the full Pydantic model to JSON
            message_body = event.model_dump_json()
            
            # Use the event type as the channel name
            channel = event.type
            
            await self._client.publish(channel, message_body)
            
            logger.debug("event_published", type=event.type, id=event.id)
            
        except Exception as e:
            logger.error("redis_publish_failed", error=str(e), event_id=event.id)
            # Depending on policy, we might raise or just log. 
            # For a broker, raising is usually better so the caller knows it failed.
            raise

    async def subscribe(self, event_type: str, handler: Callable[[SystemEvent], Coroutine[Any, Any, None]]) -> None:
        """
        Registers a local handler and subscribes to the Redis channel.
        """
        if not self._client:
            await self.connect()

        # 1. Register handler locally
        if event_type not in self._handlers:
            self._handlers[event_type] = []
            # subscribe to the actual Redis channel if it's the first time
            await self._pubsub.subscribe(event_type)
            
        self._handlers[event_type].append(handler)
        logger.info("handler_registered", event_type=event_type)

        # 2. Ensure the listener loop is running
        if not self._listener_task or self._listener_task.done():
            self._listener_task = asyncio.create_task(self._listen_loop())

    async def _listen_loop(self):
        """
        Continuous loop that pulls messages from Redis and dispatches them.
        """
        logger.info("redis_listener_loop_started")
        try:
            async for message in self._pubsub.listen():
                if message["type"] == "message":
                    await self._process_message(message)
        except asyncio.CancelledError:
            logger.info("redis_listener_cancelled")
        except Exception as e:
            logger.error("redis_listener_crashed", error=str(e))
            # In production, we'd add restart logic here (Circuit Breaker)

    async def _process_message(self, raw_msg: Dict[str, Any]):
        """
        Deserializes the Redis message and invokes registered handlers.
        """
        channel = raw_msg["channel"]
        data = raw_msg["data"]

        try:
            # 1. Deserialize to Domain Event
            # (Assumes all messages are SystemEvents)
            payload_dict = json.loads(data)
            event = SystemEvent(**payload_dict)
            
            # 2. Dispatch to handlers
            handlers = self._handlers.get(channel, [])
            for handler in handlers:
                try:
                    await handler(event)
                except Exception as handler_err:
                    # Don't let one handler crash the listener
                    logger.error("event_handler_failed", event_type=channel, error=str(handler_err))

        except Exception as e:
            logger.error("message_deserialization_failed", channel=channel, error=str(e))

    async def health_check(self) -> bool:
        if not self._client:
            return False
        try:
            return await self._client.ping()
        except Exception:
            return False