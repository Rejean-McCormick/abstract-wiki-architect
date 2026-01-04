# tests/conftest.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient

# Import the factory from the correct v2 location
from app.adapters.api.main import create_app
# Import the global container instance to ensure overrides affect the running App
from app.shared.container import container as global_container

# Split imports: Frame from models, BioFrame from frame
from app.core.domain.models import Frame
from app.core.domain.frame import BioFrame

# Import TaskQueue and LanguageRepo to support mocking
from app.core.ports import IGrammarEngine, IMessageBroker, LexiconRepo, LanguageRepo, TaskQueue

@pytest.fixture(scope="function")
def mock_grammar_engine():
    """Returns a mock implementation of the Grammar Engine."""
    engine = MagicMock(spec=IGrammarEngine)
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
    """Returns a mock that satisfies both LexiconRepo and LanguageRepo interfaces."""
    # Hybrid mock: Primarily LexiconRepo, but adding LanguageRepo methods
    repo = MagicMock(spec=LexiconRepo)
    
    # LexiconRepo methods
    repo.get_entry = AsyncMock(return_value=None)
    repo.save_entry = AsyncMock()
    repo.health_check = AsyncMock(return_value=True)
    
    # LanguageRepo methods (fixes AttributeError in onboard_language)
    repo.save_grammar = AsyncMock()
    repo.list_languages = AsyncMock(return_value=[])
    
    return repo

@pytest.fixture(scope="function")
def mock_task_queue():
    """Returns a mock TaskQueue to prevent 'Event loop closed' Redis errors."""
    # Mocking this prevents the app from trying to connect to real Redis during tests
    queue = MagicMock(spec=TaskQueue)
    queue.connect = AsyncMock()
    queue.disconnect = AsyncMock()
    queue.enqueue = AsyncMock(return_value="job_mock_123")
    
    # [FIX] Add the specific method used by BuildLanguage use case
    queue.enqueue_language_build = AsyncMock(return_value="job_build_123")
    
    return queue

@pytest.fixture(scope="function")
def container(mock_grammar_engine, mock_broker, mock_repo, mock_task_queue):
    """
    Configures the Dependency Injection Container for testing.
    We override the GLOBAL container instance used by the app.
    """
    # Override dependencies with mocks
    global_container.grammar_engine.override(mock_grammar_engine)
    global_container.message_broker.override(mock_broker)
    global_container.lexicon_repository.override(mock_repo)
    
    # Override LanguageRepo and TaskQueue
    global_container.language_repo.override(mock_repo) 
    global_container.task_queue.override(mock_task_queue)
    
    yield global_container
    
    # Clean up overrides after test to prevent pollution
    global_container.unwire()

@pytest.fixture(scope="function")
def client(container):
    """
    Returns a TestClient for integration tests.
    Arguments:
        container: Forces the container overrides to happen BEFORE the client starts.
    """
    # Instantiate the app using the v2 factory
    app = create_app()
    with TestClient(app) as c:
        yield c

@pytest.fixture
def sample_frame():
    """Provides a valid standard Frame for testing."""
    return BioFrame(
        frame_type="bio",
        subject={"name": "Alan Turing", "qid": "Q7251", "profession": "mathematician"},
        context_id="Q7251",
        meta={"tone": "formal"}
    )