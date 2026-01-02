# app/shared/container.py
from dependency_injector import containers, providers
from app.shared.config import settings

# --- Adapters ---
from app.adapters.messaging.redis_broker import RedisMessageBroker
from app.adapters.persistence.filesystem_repo import FileSystemLexiconRepository
from app.adapters.task_queue import ArqTaskQueue  # <-- ADDED

# Note: Only import S3 repo if you actually have that file, otherwise comment it out
try:
    from app.adapters.s3_repo import S3LanguageRepo
except ImportError:
    S3LanguageRepo = None

from app.adapters.engines.gf_wrapper import GFGrammarEngine
# [FIX] Swapped out the legacy/empty 'Pidgin' engine for the robust Python Wrapper
from app.adapters.engines.python_engine_wrapper import PythonGrammarEngine
from app.adapters.llm_adapter import GeminiAdapter

# --- Use Cases ---
from app.core.use_cases.generate_text import GenerateText
from app.core.use_cases.build_language import BuildLanguage
from app.core.use_cases.onboard_language_saga import OnboardLanguageSaga

class Container(containers.DeclarativeContainer):
    """
    Dependency Injection Container.
    Acts as the "Switchboard" connecting Adapters to Use Cases.
    """

    # 1. Wiring Configuration
    # This list tells dependency_injector which modules use the @inject decorator
    wiring_config = containers.WiringConfiguration(
        modules=[
            "app.adapters.api.routers.generation",
            "app.adapters.api.routers.management",
            "app.adapters.api.routers.languages",  # [RESTORED] This router exists now
            "app.adapters.api.routers.health",
            "app.adapters.api.dependencies",
            # "app.adapters.api.routers.entities", # Uncomment if you added these routers
            # "app.adapters.api.routers.frames",   # Uncomment if you added these routers
        ]
    )

    # 2. Infrastructure Gateways
    
    # Message Broker
    message_broker = providers.Singleton(RedisMessageBroker)

    # Task Queue (ARQ)
    task_queue = providers.Singleton(ArqTaskQueue)  # <-- ADDED

    # Persistence (Selector: S3 vs FileSystem)
    if settings.STORAGE_BACKEND == "s3" and S3LanguageRepo:
        language_repo = providers.Singleton(S3LanguageRepo)
    else:
        # This class now implements BOTH LanguageRepo (Metadata) and LexiconRepo (Words)
        language_repo = providers.Singleton(
            FileSystemLexiconRepository, 
            base_path=settings.FILESYSTEM_REPO_PATH
        )
    
    # Aliases for clarity (The Saga asks for 'repo', health checks ask for 'lexicon_repository')
    lexicon_repository = language_repo

    # Grammar Engine
    # [FIX] Use the PythonEngineWrapper if Mock is enabled (Fast Strategy)
    if settings.USE_MOCK_GRAMMAR:
        grammar_engine = providers.Singleton(PythonGrammarEngine)
    else:
        grammar_engine = providers.Singleton(GFGrammarEngine, lib_path=settings.GF_LIB_PATH)

    # LLM Client (Gemini BYOK)
    llm_client = providers.Singleton(GeminiAdapter)

    # 3. Use Cases (Application Logic)
    
    generate_text_use_case = providers.Factory(
        GenerateText,
        # Named argument must match GenerateText.__init__(self, engine, ...)
        engine=grammar_engine,
        # Optional: Inject LLM if you want refinement enabled
        # llm=llm_client 
    )

    build_language_use_case = providers.Factory(
        BuildLanguage,
        task_queue=task_queue  # <-- FIX: Injects task_queue instead of broker
    )

    onboard_language_saga = providers.Factory(
        OnboardLanguageSaga,
        broker=message_broker,
        repo=language_repo 
    )

# Global Container Instance
container = Container()