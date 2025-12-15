# app\core\ports\grammar_engine.py
from typing import Protocol, List, Optional
from app.core.domain.models import Frame, Sentence

class IGrammarEngine(Protocol):
    """
    Port for the Natural Language Generation engine.
    Implementations:
    - GFWrapper (Adapts the binary 'Wiki.pgf' via the C API)
    - PythonEngineWrapper (Adapts the pure Python engines)
    """

    async def generate(self, lang_code: str, frame: Frame) -> Sentence:
        """
        Transforms a Semantic Frame into a linear text string.
        
        Args:
            lang_code: The target language ISO 639-3 code.
            frame: The abstract semantic representation.
            
        Returns:
            A Sentence object containing the text and debug metadata.
            
        Raises:
            LanguageNotFoundError: If the language is not loaded in the engine.
            GrammarCompilationError: If the engine fails internally.
        """
        ...

    async def get_supported_languages(self) -> List[str]:
        """Returns a list of ISO codes currently loaded in the engine."""
        ...

    async def reload(self) -> None:
        """Forces the engine to reload resources (e.g., after a new PGF build)."""
        ...

    async def health_check(self) -> bool:
        """Returns True if the engine is responsive."""
        ...