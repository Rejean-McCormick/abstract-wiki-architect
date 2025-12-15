# app\adapters\messaging\__init__.py
"""
Messaging Adapters.

This package contains the concrete implementations of the `IMessageBroker` port.
It handles the connection to external message queues/brokers.

Components:
- RedisMessageBroker: Implementation using Redis Pub/Sub for lightweight event streaming.
"""

from .redis_broker import RedisMessageBroker

__all__ = [
    "RedisMessageBroker",
]