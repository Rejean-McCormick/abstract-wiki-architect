# tests\core\test_use_cases.py
import pytest
from unittest.mock import AsyncMock, any_call
from app.core.domain.models import Sentence, Frame, EventType
from app.core.domain.exceptions import InvalidFrameError, DomainError

@pytest.mark.asyncio
class TestGenerateText:
    
    async def test_execute_success(self, container, mock_grammar_engine, sample_frame):
        """
        Scenario: A valid frame is provided, and the engine returns text.
        Expected: The use case returns a Sentence object and calls the engine.
        """
        # Arrange
        use_case = container.generate_text_use_case()
        expected_text = "Alan Turing is a Mathematician."
        
        # Mock the engine response
        mock_grammar_engine.generate.return_value = Sentence(
            text=expected_text, 
            lang_code="eng"
        )

        # Act
        result = await use_case.execute("eng", sample_frame)

        # Assert
        assert result.text == expected_text
        assert result.lang_code == "eng"
        mock_grammar_engine.generate.assert_called_once_with("eng", sample_frame)

    async def test_execute_invalid_frame(self, container):
        """
        Scenario: A frame missing required fields (frame_type) is provided.
        Expected: Raises InvalidFrameError immediately (Fail Fast).
        """
        # Arrange
        use_case = container.generate_text_use_case()
        invalid_frame = Frame(frame_type="", subject={}) # Empty type is invalid

        # Act & Assert
        with pytest.raises(InvalidFrameError):
            await use_case.execute("eng", invalid_frame)

    async def test_execute_engine_failure(self, container, mock_grammar_engine, sample_frame):
        """
        Scenario: The grammar engine throws an unexpected infrastructure exception.
        Expected: The Use Case catches it and wraps it in a DomainError.
        """
        # Arrange
        use_case = container.generate_text_use_case()
        mock_grammar_engine.generate.side_effect = Exception("GF Runtime Crash")

        # Act & Assert
        with pytest.raises(DomainError) as excinfo:
            await use_case.execute("eng", sample_frame)
        
        assert "Unexpected generation failure" in str(excinfo.value)


@pytest.mark.asyncio
class TestBuildLanguage:

    async def test_execute_success(self, container, mock_broker):
        """
        Scenario: A valid build request is made.
        Expected: Returns an event ID and publishes a BUILD_REQUESTED event to the broker.
        """
        # Arrange
        use_case = container.build_language_use_case()
        lang = "deu"
        strategy = "fast"

        # Act
        event_id = await use_case.execute(lang, strategy)

        # Assert
        assert event_id is not None
        assert isinstance(event_id, str)
        
        # Verify broker published the correct event
        assert mock_broker.publish.called
        
        # Inspect the event object passed to publish
        published_event = mock_broker.publish.call_args[0][0]
        assert published_event.type == EventType.BUILD_REQUESTED
        assert published_event.payload["lang_code"] == lang
        assert published_event.payload["strategy"] == strategy

    async def test_execute_invalid_strategy(self, container):
        """
        Scenario: An invalid build strategy is requested.
        Expected: Raises DomainError.
        """
        # Arrange
        use_case = container.build_language_use_case()

        # Act & Assert
        with pytest.raises(DomainError) as excinfo:
            await use_case.execute("deu", strategy="magic_wand")
        
        assert "Invalid build strategy" in str(excinfo.value)