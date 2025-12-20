# app/core/use_cases/generate_text.py
import structlog
from typing import Optional
from opentelemetry import trace

from app.core.domain.models import Frame, Sentence
from app.core.domain.exceptions import InvalidFrameError, DomainError
from app.core.ports.grammar_engine import IGrammarEngine
from app.core.ports.llm_port import ILanguageModel
from app.shared.observability import get_tracer

logger = structlog.get_logger()
tracer = get_tracer(__name__)

class GenerateText:
    """
    Use Case: Converts an Abstract Semantic Frame into natural language text.
    
    Responsibilities:
    1. Validates the input Frame structure.
    2. Selects the appropriate Grammar Engine via the Port.
    3. Traces the generation process for observability.
    4. Handles domain-level errors.
    """

    def __init__(self, engine: IGrammarEngine, llm: Optional[ILanguageModel] = None):
        # We inject the interfaces (Ports), not the concrete implementations
        self.engine = engine
        self.llm = llm

    async def execute(self, lang_code: str, frame: Frame) -> Sentence:
        """
        Executes the text generation logic.

        Args:
            lang_code: ISO 639-3 code (e.g., 'fra').
            frame: The semantic intent (Frame domain entity).

        Returns:
            Sentence: The generated text entity.
        """
        with tracer.start_as_current_span("use_case.generate_text") as span:
            span.set_attribute("app.lang_code", lang_code)
            span.set_attribute("app.frame_type", frame.frame_type)
            
            logger.info("generation_started", lang=lang_code, frame_type=frame.frame_type)

            try:
                # 1. Validation (Business Rules)
                self._validate_frame(frame)

                # 2. Execution (via Grammar Engine Port)
                # The core doesn't know if this runs GF binary or Python code.
                sentence = await self.engine.generate(lang_code, frame)
                
                # 3. Refinement (Optional LLM Step)
                # If an LLM is present, we could refine the grammar output here.
                # if self.llm:
                #     sentence.text = await self.llm.refine(sentence.text)
                
                # 4. Post-processing / Metrics
                span.set_attribute("app.generated_length", len(sentence.text))
                logger.info("generation_success", lang=lang_code, text_preview=sentence.text[:50])
                
                return sentence

            except DomainError:
                # Re-raise known domain errors (LanguageNotFound, etc.)
                raise
            except Exception as e:
                # Catch unexpected infrastructure errors and log them
                logger.error("generation_failed", error=str(e), exc_info=True)
                # We typically wrap unknown errors in a generic DomainError to keep the API clean
                raise DomainError(f"Unexpected generation failure: {str(e)}")

    def _validate_frame(self, frame: Frame):
        """
        Enforces strict semantic rules before attempting generation.
        """
        if not frame.frame_type:
            raise InvalidFrameError("Frame must have a 'frame_type'.")
        
        # Example: Bio frames must have a subject name
        if frame.frame_type == "bio" and "name" not in frame.subject:
             raise InvalidFrameError("BioFrame requires a subject with a 'name' field.")