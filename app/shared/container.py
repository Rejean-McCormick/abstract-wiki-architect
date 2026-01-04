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
    wiring_config = containers.WiringConfiguration(
        modules=[
            "app.adapters.api.routers.generation",
            "app.adapters.api.routers.management",
            "app.adapters.api.routers.languages",
            "app.adapters.api.routers.health",
            "app.adapters.api.dependencies",
        ]
    )

    # 2. Infrastructure Gateways

    # Message Broker
    message_broker = providers.Singleton(RedisMessageBroker)

    # Task Queue (ARQ)
    task_queue = providers.Singleton(ArqTaskQueue)

    # Persistence (Selector: S3 vs FileSystem)
    if settings.STORAGE_BACKEND == "s3" and S3LanguageRepo:
        language_repo = providers.Singleton(S3LanguageRepo)
    else:
        language_repo = providers.Singleton(
            FileSystemLexiconRepository,
            base_path=settings.FILESYSTEM_REPO_PATH,
        )

    # Aliases for clarity
    lexicon_repository = language_repo

    # Grammar Engine
    if settings.USE_MOCK_GRAMMAR:
        grammar_engine = providers.Singleton(PythonGrammarEngine)
    else:
        grammar_engine = providers.Singleton(GFGrammarEngine, lib_path=settings.GF_LIB_PATH)

    # LLM Client (Gemini BYOK)
    llm_client = providers.Singleton(GeminiAdapter)

    # 3. Use Cases (Application Logic)

    generate_text_use_case = providers.Factory(
        GenerateText,
        engine=grammar_engine,
        # llm=llm_client
    )

    # ✅ FIX: inject BOTH the task queue and the broker
    build_language_use_case = providers.Factory(
        BuildLanguage,
        task_queue=task_queue,
        broker=message_broker,
    )

    onboard_language_saga = providers.Factory(
        OnboardLanguageSaga,
        broker=message_broker,
        repo=language_repo,
    )


# Global Container Instance
container = Container()
