# app\worker\tasks.py
import asyncio
import structlog
from dependency_injector.wiring import inject, Provide

from app.shared.container import Container
from app.core.domain.events import SystemEvent, BuildRequestedPayload
from app.core.domain.models import LanguageStatus
from app.core.ports.lexicon_repository import ILexiconRepository
from app.core.ports.grammar_engine import IGrammarEngine
from app.worker.settings import worker_settings

logger = structlog.get_logger()

class BuildTaskHandler:
    """
    Handler for the 'language.build.requested' event.
    
    Responsibilities:
    1. Parse the build request.
    2. Update Language status to 'BUILDING'.
    3. Execute the build strategy (CPU bound).
    4. Update Language status to 'READY'.
    5. Trigger a hot-reload of the Grammar Engine.
    """
    
    @inject
    async def handle(
        self, 
        event: SystemEvent,
        repo: ILexiconRepository = Provide[Container.lexicon_repository],
        engine: IGrammarEngine = Provide[Container.grammar_engine]
    ):
        ctx = structlog.contextvars.bind_contextvars(event_id=event.id)
        
        try:
            # 1. Parse Payload
            payload = BuildRequestedPayload(**event.payload)
            lang_code = payload.lang_code
            strategy = payload.strategy
            
            logger.info("worker_build_started", lang=lang_code, strategy=strategy)

            # 2. Update Status -> BUILDING (Simulated for this MVP)
            # await repo.update_status(lang_code, LanguageStatus.BUILDING)
            
            # 3. Execute Build Logic
            if strategy == "full":
                await self._perform_full_compilation(lang_code)
            else:
                await self._perform_fast_scaffolding(lang_code)

            # 4. Update Status -> READY
            # await repo.update_status(lang_code, LanguageStatus.READY)

            # 5. Hot Reload the Engine (if applicable)
            # This ensures the API starts serving the new language immediately
            if strategy == "full":
                 await engine.reload()

            logger.info("worker_build_success", lang=lang_code)

        except Exception as e:
            logger.error("worker_build_failed", error=str(e), exc_info=True)
            # In a real system, we would publish a BUILD_FAILED event here
            # and update the repo status to ERROR.
        finally:
            structlog.contextvars.clear_contextvars()

    async def _perform_full_compilation(self, lang_code: str):
        """
        Simulates the heavy GF compilation process.
        In reality, this would run `subprocess.run(['gf', '-make', ...])`.
        """
        logger.info("compiling_gf_grammar", lang=lang_code)
        # Simulate CPU work
        await asyncio.sleep(5) 
        # Here we would check the exit code of the compiler
        return True

    async def _perform_fast_scaffolding(self, lang_code: str):
        """
        Simulates generating the Python/JSON scaffolding.
        """
        logger.info("scaffolding_fast_grammar", lang=lang_code)
        await asyncio.sleep(1)
        return True