# app\adapters\redis_broker.py
# app/adapters/redis_broker.py
import json
import logging
from typing import Any, Dict

import redis.asyncio as redis
from opentelemetry import trace
from opentelemetry.propagate import inject

from app.core.ports import EventBroker
from app.shared.config import settings
from app.shared.telemetry import get_tracer

logger = logging.getLogger(__name__)
tracer = get_tracer(__name__)

class RedisEventBroker(EventBroker):
    """
    Driven Adapter: Publishes Domain Events to Redis Pub/Sub.
    Enhancement: Injects OpenTelemetry Trace Context for distributed tracing.
    """

    def __init__(self):
        # Initialize async Redis client using the shared config URL
        self.redis_url = settings.redis_url
        self.client = redis.from_url(
            self.redis_url, 
            encoding="utf-8", 
            decode_responses=True
        )

    async def publish(self, channel: str, event_type: str, payload: Dict[str, Any]) -> None:
        """
        Publishes a structured event to a Redis Channel.
        """
        with tracer.start_as_current_span("redis_publish") as span:
            span.set_attribute("messaging.system", "redis")
            span.set_attribute("messaging.destination", channel)
            span.set_attribute("messaging.event_type", event_type)

            # 1. Prepare the Envelope
            message_envelope = {
                "event": event_type,
                "payload": payload,
                "meta": {
                    "producer": settings.APP_NAME,
                    "env": settings.APP_ENV,
                    "trace_context": {} 
                }
            }

            # 2. Inject Distributed Trace Context
            # This allows the Worker (consumer) to link its span to this parent span.
            inject(message_envelope["meta"]["trace_context"])

            # 3. Serialize and Publish
            try:
                json_message = json.dumps(message_envelope)
                await self.client.publish(channel, json_message)
                logger.debug(f"Published {event_type} to {channel}")
            except Exception as e:
                logger.error(f"Failed to publish event to Redis: {e}")
                # We usually don't raise here to prevent blocking the main flow,
                # unless strict event consistency is required.
                span.record_exception(e)

    async def close(self):
        """Gracefully closes the Redis connection."""
        await self.client.close()