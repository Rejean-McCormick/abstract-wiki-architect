import json
import logging
from typing import Optional
from redis.asyncio import Redis, from_url
from app.shared.config import settings
from app.core.domain.context import SessionContext

logger = logging.getLogger(settings.OTEL_SERVICE_NAME)

class RedisBus:
    """
    Adapter for Redis interactions.
    Handles connection pooling and JSON serialization for SessionContext.
    """
    def __init__(self) -> None:
        self._redis: Optional[Redis] = None

    async def connect(self) -> None:
        """Initializes the Redis connection pool."""
        if not self._redis:
            logger.info("Connecting to Redis...", extra={"url": settings.REDIS_URL})
            self._redis = from_url(settings.REDIS_URL, decode_responses=True)

    async def close(self) -> None:
        """Closes the connection pool."""
        if self._redis:
            await self._redis.close()

    async def get_session(self, session_id: str) -> SessionContext:
        """
        Retrieves the Discourse Context for a given session.
        Returns an empty context if the key does not exist.
        """
        if not self._redis:
            await self.connect()

        key = f"awa:session:{session_id}"
        data = await self._redis.get(key)
        
        if data:
            try:
                # Rehydrate the JSON string back into the Pydantic model
                return SessionContext.model_validate_json(data)
            except Exception as e:
                logger.error(f"Failed to parse session context: {e}")
        
        # Return a fresh context if missing or corrupted
        return SessionContext(session_id=session_id)

    async def save_session(self, context: SessionContext) -> None:
        """
        Persists the updated Discourse Context.
        Resets the TTL to keep the session alive.
        """
        if not self._redis:
            await self.connect()

        key = f"awa:session:{context.session_id}"
        
        # Serialize to JSON string
        payload = context.model_dump_json()
        
        # Atomic SET with Expiry
        await self._redis.set(key, payload, ex=settings.SESSION_TTL_SEC)

# Global Singleton
redis_bus = RedisBus()