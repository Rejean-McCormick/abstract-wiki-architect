# tests\conftest.py
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.shared.container import Container
from app.core.domain.models import Frame, FrameType
from app.core.ports.grammar_engine import IGrammarEngine
from app.core.ports.message_broker import IMessageBroker
from app.core.ports.lexicon_repository import ILexiconRepository

@pytest.fixture(scope="function")
def mock_grammar_engine():
    """Returns a mock implementation of the Grammar Engine."""
    engine = MagicMock(spec=IGrammarEngine)
    # Async methods must be mocked with AsyncMock
    engine.generate = AsyncMock()
    engine.get_supported_languages = AsyncMock(return_value=["eng", "fra"])
    engine.reload = AsyncMock()
    engine.health_check = AsyncMock(return_value=True)
    return engine

@pytest.fixture(scope="function")
def mock_broker():
    """Returns a mock Message Broker."""
    broker = MagicMock(spec=IMessageBroker)
    broker.publish = AsyncMock()
    broker.subscribe = AsyncMock()
    broker.connect = AsyncMock()
    broker.disconnect = AsyncMock()
    broker.health_check = AsyncMock(return_value=True)
    return broker

@pytest.fixture(scope="function")
def mock_repo():
    """Returns a mock Lexicon Repository."""
    repo = MagicMock(spec=ILexiconRepository)
    repo.get_entry = AsyncMock(return_value=None)
    repo.save_entry = AsyncMock()
    repo.health_check = AsyncMock(return_value=True)
    return repo

@pytest.fixture(scope="function")
def container(mock_grammar_engine, mock_broker, mock_repo):
    """
    Sets up the Dependency Injection Container for testing.
    It overrides real infrastructure providers with the mocks defined above.
    """
    container = Container()
    
    # Override dependencies with mocks
    container.grammar_engine.override(mock_grammar_engine)
    container.message_broker.override(mock_broker)
    container.lexicon_repository.override(mock_repo)
    
    # Wire the container if necessary (though usually needed only for @inject)
    # container.wire(modules=[...]) 
    
    yield container
    
    # Clean up overrides after test
    container.unwire()

@pytest.fixture
def sample_frame():
    """Provides a valid standard Frame for testing."""
    return Frame(
        frame_type="bio",
        subject={"name": "Alan Turing", "qid": "Q7251"},
        properties={"occupation": "Mathematician"},
        meta={"tone": "formal"}
    )