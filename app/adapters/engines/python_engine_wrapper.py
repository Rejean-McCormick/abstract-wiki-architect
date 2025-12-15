# app\adapters\engines\python_engine_wrapper.py
import structlog
from typing import List, Dict, Any
from app.core.ports.grammar_engine import IGrammarEngine
from app.core.domain.models import Frame, Sentence
from app.core.domain.exceptions import UnsupportedFrameTypeError

logger = structlog.get_logger()

class PythonGrammarEngine(IGrammarEngine):
    """
    Implementation of the Grammar Engine using pure Python.
    
    Strategy: 'Fast' / 'Pidgin'
    Use Case: Scaffolding new languages, Debugging, High-performance requirements.
    
    It maps semantic frames to simple f-string templates. 
    It lacks the sophisticated linearization (agreement, morphology) of GF.
    """

    def __init__(self):
        # In a real scenario, these templates might be loaded from JSON files
        # or python modules in `language_profiles/`.
        self._templates = {
            "bio": "{subject} is a {profession} from {origin}.",
            "event": "{subject} participated in {event} on {date}."
        }
        self._supported_langs = ["eng", "debug"]

    async def generate(self, lang_code: str, frame: Frame) -> Sentence:
        """
        Generates text using simple variable substitution.
        """
        # 1. Select Template
        template = self._templates.get(frame.frame_type)
        if not template:
            raise UnsupportedFrameTypeError(frame.frame_type)

        # 2. Flatten Data for Template
        # We merge subject info, properties, and meta into one dict for the f-string
        data = {
            **frame.subject,
            **frame.properties,
            **frame.meta
        }
        
        # Defaulting missing keys to '???' to make errors visible in output
        safe_data = SafeDict(data)

        # 3. Render
        try:
            text = template.format_map(safe_data)
        except Exception as e:
            logger.error("python_render_failed", error=str(e))
            text = f"[Error rendering {frame.frame_type}]"

        # 4. Return Sentence Entity
        return Sentence(
            text=text,
            lang_code=lang_code,
            debug_info={
                "engine": "python_fast",
                "template_used": template
            }
        )

    async def get_supported_languages(self) -> List[str]:
        return self._supported_langs

    async def reload(self) -> None:
        # No-op for Python engine as it doesn't hold heavy binaries
        pass

    async def health_check(self) -> bool:
        return True

class SafeDict(dict):
    """Helper to return a placeholder for missing keys during string formatting."""
    def __missing__(self, key):
        return f"<{key}?>"