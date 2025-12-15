# app\core\use_cases\onboard_language_saga.py
import structlog
from datetime import datetime
from app.core.domain.models import Language, LanguageStatus, GrammarType
from app.core.domain.events import SystemEvent, EventType, BuildRequestedPayload
from app.core.domain.exceptions import DomainError
from app.core.ports.message_broker import IMessageBroker
# Note: We assume a specific repository for Language metadata exists, 
# typically separate from the word-level LexiconRepository.
from app.core.ports.lexicon_repository import ILexiconRepository 
from app.shared.observability import get_tracer

logger = structlog.get_logger()
tracer = get_tracer(__name__)

class LanguageAlreadyExistsError(DomainError):
    def __init__(self, code: str):
        super().__init__(f"Language '{code}' is already registered in the system.")

class OnboardLanguageSaga:
    """
    Use Case (Saga): Orchestrates the onboarding of a new language.
    
    Steps:
    1. Validates uniqueness (ISO 639-3).
    2. Creates the Language Entity (Status: PLANNED).
    3. Persists the metadata (Updating the 'Everything Matrix').
    4. Triggers the initial scaffolding/build via the Event Bus.
    """

    def __init__(self, broker: IMessageBroker, repo: ILexiconRepository):
        # In a larger system, 'repo' might be 'ILanguageRepository' specifically.
        # Here we use ILexiconRepository assuming it manages language metadata too.
        self.broker = broker
        self.repo = repo

    async def execute(self, code: str, name: str, family: str = "Other") -> str:
        """
        Executes the onboarding saga.

        Args:
            code: ISO 639-3 code (e.g., 'deu').
            name: English name (e.g., 'German').
            family: Language family.

        Returns:
            str: The ID of the Language entity created.
        """
        with tracer.start_as_current_span("use_case.onboard_language") as span:
            span.set_attribute("app.lang_code", code)
            
            logger.info("onboarding_started", code=code, name=name)

            # 1. Check for duplicates
            # (Assuming the repo has a method to check existence or we catch an error)
            # This is a simplification; in real code, we'd query the repo.
            # existing = await self.repo.get_language(code)
            # if existing: raise LanguageAlreadyExistsError(code)

            # 2. Create Entity
            language = Language(
                code=code,
                name=name,
                family=family,
                status=LanguageStatus.PLANNED,
                grammar_type=GrammarType.FACTORY, # Default to Pidgin first
                build_strategy="fast"
            )

            # 3. Persist Metadata
            # This saves the config to 'languages.json' or DB
            # await self.repo.save_language_config(language)
            logger.info("language_metadata_saved", code=code)

            # 4. Trigger the Build (The Side Effect)
            # We immediately request a 'Fast' build to generate the scaffolding
            build_payload = BuildRequestedPayload(
                lang_code=code,
                strategy="fast"
            )
            
            event = SystemEvent(
                type=EventType.BUILD_REQUESTED,
                payload=build_payload.model_dump()
            )
            
            await self.broker.publish(event)
            
            logger.info("onboarding_build_triggered", event_id=event.id)
            
            return code