# app/shared/container.py
from dependency_injector import containers, providers

from app.shared.config import settings

# --- Adapters ---
from app.adapters.llm_adapter import GeminiAdapter
from app.adapters.messaging.redis_broker import RedisMessageBroker
from app.adapters.persistence.filesystem_repo import FileSystemLexiconRepository
from app.adapters.task_queue import ArqTaskQueue
from app.adapters.engines.gf_wrapper import GFGrammarEngine
from app.adapters.engines.python_engine_wrapper import PythonGrammarEngine

try:
    from app.adapters.s3_repo import S3LanguageRepo
except ImportError:
    S3LanguageRepo = None


# --- Use Cases ---
from app.core.use_cases.generate_text import GenerateText
from app.core.use_cases.build_language import BuildLanguage
from app.core.use_cases.onboard_language_saga import OnboardLanguageSaga


_STORAGE_BACKEND = (settings.STORAGE_BACKEND or "").strip().lower()
_USE_S3_REPO = _STORAGE_BACKEND == "s3" and S3LanguageRepo is not None


class Container(containers.DeclarativeContainer):
    """
    Dependency Injection container.

    Notes:
    - PGF_PATH is the source of truth for the compiled grammar.
    - Do NOT pass settings.GF_LIB_PATH into GFGrammarEngine; that points at the
      GF library tree, not the compiled semantik_architect.pgf artifact.
    - GeminiAdapter is request-scoped. API dependencies should pass a per-request
      adapter into `generate_text_use_case(...)` when BYOK headers are present.
    """

    wiring_config = containers.WiringConfiguration(
        modules=[
            "app.adapters.api.routers.generation",
            "app.adapters.api.routers.management",
            "app.adapters.api.routers.languages",
            "app.adapters.api.routers.health",
            "app.adapters.api.dependencies",
        ]
    )

    # Optional: expose settings to providers/tests
    config = providers.Object(settings)

    # --- Infrastructure ---
    message_broker = providers.Singleton(RedisMessageBroker)

    task_queue = providers.Singleton(
        ArqTaskQueue,
        redis_dsn=settings.REDIS_URL,
        queue_name=settings.REDIS_QUEUE_NAME,
    )

    if _USE_S3_REPO:
        language_repo = providers.Singleton(S3LanguageRepo)
    else:
        language_repo = providers.Singleton(
            FileSystemLexiconRepository,
            base_path=settings.FILESYSTEM_REPO_PATH,
        )

    # Alias retained for compatibility/readability
    lexicon_repository = language_repo

    if settings.USE_MOCK_GRAMMAR:
        grammar_engine = providers.Singleton(PythonGrammarEngine)
    else:
        # Let GFGrammarEngine resolve settings.PGF_PATH by itself.
        grammar_engine = providers.Singleton(GFGrammarEngine)

    # Request-scoped adapter factory.
    # Usage from dependencies.py:
    #   llm = container.llm_adapter(user_api_key=user_key)
    llm_adapter = providers.Factory(GeminiAdapter)

    # --- Use Cases ---
    # Keep this override-friendly: request-specific LLM instances can be supplied
    # at call time, e.g. container.generate_text_use_case(llm=llm).
    generate_text_use_case = providers.Factory(
        GenerateText,
        engine=grammar_engine,
    )

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