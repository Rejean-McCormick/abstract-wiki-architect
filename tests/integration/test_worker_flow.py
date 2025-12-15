# tests\integration\test_worker_flow.py
import pytest
from unittest.mock import AsyncMock, patch
from app.core.domain.events import EventType, SystemEvent
from app.worker.tasks import BuildTaskHandler

@pytest.mark.asyncio
class TestWorkerFlow:
    """
    Integration-style test verifying the Event -> Worker -> Domain logic flow.
    """

    async def test_build_event_handling(self, container, mock_grammar_engine, mock_repo):
        """
        Scenario: A 'BUILD_REQUESTED' event arrives at the Worker.
        Expected: 
        1. The event payload is parsed.
        2. The grammar engine 'reload' method is called (for full strategy).
        3. Logging confirms success.
        """
        # Arrange
        handler = BuildTaskHandler()
        
        # Construct a raw event as it would come from Redis
        event_payload = {
            "lang_code": "deu",
            "strategy": "full"
        }
        
        event = SystemEvent(
            type=EventType.BUILD_REQUESTED,
            payload=event_payload
        )

        # Act
        # We manually invoke the handler, simulating the Redis listener loop
        await handler.handle(event)

        # Assert
        
        # 1. Verify Engine Interaction (The core "Job" of the worker)
        # For 'full' strategy, we expect a reload
        mock_grammar_engine.reload.assert_called_once()
        
        # 2. Verify Logging (Optional but useful)
        # We can check if structlog context vars were set or if specific logs were emitted
        # but that requires capturing logs. For now, asserting the side-effect (engine reload) is sufficient.

    async def test_build_event_fast_strategy(self, container, mock_grammar_engine):
        """
        Scenario: A 'fast' strategy build event arrives.
        Expected: The engine is NOT reloaded (since fast builds are just JSON generation).
        """
        # Arrange
        handler = BuildTaskHandler()
        event = SystemEvent(
            type=EventType.BUILD_REQUESTED,
            payload={"lang_code": "deu", "strategy": "fast"}
        )

        # Act
        await handler.handle(event)

        # Assert
        mock_grammar_engine.reload.assert_not_called()

    async def test_worker_graceful_failure(self, container, mock_grammar_engine):
        """
        Scenario: The handler encounters an exception (e.g. Engine crash).
        Expected: The exception is logged/caught, ensuring the worker loop doesn't crash.
        """
        # Arrange
        handler = BuildTaskHandler()
        event = SystemEvent(
            type=EventType.BUILD_REQUESTED,
            payload={"lang_code": "deu", "strategy": "full"}
        )
        
        # Simulate a crash in the domain logic
        # Note: We mock the private method or the engine dependency
        mock_grammar_engine.reload.side_effect = Exception("Compilation Failed")

        # Act
        # The handle method wraps logic in try/except, so it should NOT raise.
        await handler.handle(event)

        # Assert
        # If we reached here, the worker didn't crash. 
        mock_grammar_engine.reload.assert_called_once()