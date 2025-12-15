# app\shared\container.py
from dependency_injector import containers, providers

from app.shared.config import settings
from app.adapters.messaging.redis_broker import RedisMessageBroker
from app.adapters.persistence.filesystem_repo import FileSystemLexiconRepository
from app.adapters.engines.gf_wrapper import GFGrammarEngine
# We can optionally wire the Python engine as a fallback or alternative
from app.adapters.engines.python_engine_wrapper import PythonGrammarEngine

from app.core.use_cases.generate_text import GenerateText
from app.core.use_cases.build_language import BuildLanguage
from app.core.use_cases.onboard_language_saga import OnboardLanguageSaga

class Container(containers.DeclarativeContainer):
    """
    Dependency Injection Container.
    
    This declarative container defines the assembly instructions for the application.
    """

    # 1. Configuration
    # We load settings directly, but wrapping them allows overriding in tests.
    config = providers.Configuration(pydantic_settings=[settings])

    # 2. Gateways (Infrastructure Adapters)
    
    # Message Broker (Singleton: One connection pool shared)
    message_broker = providers.Singleton(
        RedisMessageBroker
    )

    # Persistence (Singleton: One access point to files)
    lexicon_repository = providers.Singleton(
        FileSystemLexiconRepository
    )

    # Grammar Engine (Singleton: Loads the heavy PGF binary once)
    # In a more complex setup, this could be a 'Selector' provider that chooses 
    # between GF and Python based on a config flag.
    grammar_engine = providers.Singleton(
        GFGrammarEngine
    )
    
    # Optional: Bronze-tier engine
    # python_engine = providers.Singleton(PythonGrammarEngine)

    # 3. Use Cases (Application Logic)
    
    # Factory: New instance created for every request (stateless logic),
    # but with Singleton dependencies injected.
    
    generate_text_use_case = providers.Factory(
        GenerateText,
        grammar_engine=grammar_engine
    )

    build_language_use_case = providers.Factory(
        BuildLanguage,
        broker=message_broker
    )

    onboard_language_saga = providers.Factory(
        OnboardLanguageSaga,
        broker=message_broker,
        repo=lexicon_repository
    )

# Instantiate the container for global access (e.g. by FastAPI)
container = Container()