# app\core\ports\message_broker.py
from typing import Protocol, Any, Callable, Coroutine
from app.core.domain.events import SystemEvent

class IMessageBroker(Protocol):
    """
    Port for the Event Bus.
    
    Allows the Core Logic to publish Domain Events and allows the Worker
    to subscribe to them.
    """

    async def publish(self, event: SystemEvent) -> None:
        """
        Publishes a domain event to the message broker.
        
        Args:
            event: The fully typed SystemEvent object.
        """
        ...

    async def subscribe(self, event_type: str, handler: Callable[[SystemEvent], Coroutine[Any, Any, None]]) -> None:
        """
        Registers a callback function to be executed when a specific event type occurs.
        
        Args:
            event_type: The string identifier of the event (e.g., 'language.build.requested').
            handler: An async function that takes a SystemEvent and processes it.
        """
        ...

    async def health_check(self) -> bool:
        """Returns True if the broker is connected and reachable."""
        ...